"""Integrated interpreter + simulation visualization.

Loads a SysML v2 model and runs it against a real simulation model (e.g.
Fischertechnik's `Factory`), on two threads:

- Main thread: the selected domain's own `SimulationVisualization.run()`
  (pygame requires this).
- Background thread: the interpreter's reactive loop, re-evaluating every
  `ExecutableStateUsage` on a tick.

Nothing runs until `on_start` is called in the simulation visualization. This `on_start`
just releases the interpreter thread, which then does the model's eager part-instantiation pass itself
and starts stepping.

Add a new simulation domain by adding one entry to `SIMULATION_MODELS`
below -- nothing else in this file needs to change.
"""

import argparse
import itertools
import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional

from core.language import Scenario
from core.vm import ProgramUpdateOption, VirtualMachine
from languages.sysmlv2.update_inbox import InboxState, UpdateFileError, UpdateInbox
from languages.sysmlv2.updates import AtomicUpdate
from languages.sysmlv2.simulation_models.facade_proxy import SimulationBridge, ThreadChannel
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import FischertechnikVisualization
from languages.sysmlv2.simulation_models.generic import BaseSimulationModel, LiveUpdateState, SimulationVisualization
from tools.load_sysml import load

# Where update files are dropped during a live demo (see updates/README.md); --updates-dir overrides it.
DEFAULT_UPDATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "updates")

# A Dict describing what Simulation Model and Visualization is ready to be used as part of this CLI
REGISTERED_SIMULATION_MODELS: dict[str, tuple[type[BaseSimulationModel], type[SimulationVisualization]]] = {
    "fischertechnik": (Factory, FischertechnikVisualization),
}

def build_simulation(sysml_path: str, simulation_model_class: type[BaseSimulationModel]) -> tuple[VirtualMachine, BaseSimulationModel]:
    """Loads the SysML model (represented by `sysml_path), constructs a fresh instance of `BaseSimulationModel`,
    and a fresh LipVM virtual machine. Deliberately doesn't step the virtual machine, it waits until it is started
    through the Main thread (Simulation Visualization thread).

    sysml_path: Path to the SysML model to be loaded (format .sysml)
    simulation_model_class: the actual simulation model class to be used
    """
    resource = load(sysml_path, keep_xmi=False)
    scenario = Scenario(program_definition=resource.contents[0])

    vm = VirtualMachine()
    vm.scenario = scenario
    vm.init()

    model = simulation_model_class()

    return vm, model

@dataclass(frozen=True)
class SubmittedUpdate:
    """An update file's updates on their way to the interpreter thread
    (window -> interpreter, `update_queue`): `name` is the file's name, for
    messages; `update` its `UPDATES` as one AtomicUpdate (see
    languages/sysmlv2/update_inbox.py)."""
    name: str
    update: AtomicUpdate

@dataclass(frozen=True)
class UpdateStatus:
    """What became of a SubmittedUpdate (interpreter -> window,
    `update_results`): `kind` is "submitted" (now pending in the VM, waiting
    for tranquility) or "rejected" (it can't be applied, never reached the
    VM); `message` says more."""
    kind: str
    name: str
    message: str

def _hand_over_update(vm: VirtualMachine, update_queue: queue.Queue, update_results: queue.Queue) -> None:
    """Between two `vm.step()` calls, on the interpreter thread: if no update
    is pending (the VM holds one at a time), takes the next queued one,
    checks it against the running model and submits it.

    Checked here, before `vm.submit`, because the registry belongs to this
    thread, and because an update that fails inside `apply()` would raise out
    of `vm.step()`, ending this thread and staying pending. Only the errors a
    wrong update file produces are caught (`LookupError`: unknown part or
    attribute; `ValueError`: a part def as owner); anything else is a bug and
    is raised.
    """
    if vm.has_pending_update():
        return
    try:
        item = update_queue.get_nowait()
    except queue.Empty:
        return

    try:
        item.update.check(vm.state)
        item.update.affected_elements(vm.state)
    except (LookupError, ValueError) as error:
        status = UpdateStatus("rejected", item.name, str(error))
    else:
        vm.submit(item.update, ProgramUpdateOption.HOTSWAP)
        status = UpdateStatus("submitted", item.name,
                              f"{len(item.update.updates)} update(s) pending, waiting for tranquility")
    print(f"Update {item.name} {status.kind}: {status.message}")
    update_results.put(status)

WAITING_MESSAGE = "There is an update to the model. Waiting to reach tranquility"

class LiveUpdateControl:
    """The driver's side of the update button (main thread): what the
    visualization shows, asked every frame (`state`), and what a click does
    (`submit`).

    The button is enabled when the update folder holds exactly one update
    file and no update is on its way: neither pending in the VM nor
    submitted and still waiting for the interpreter thread to take it. A
    click loads the file into one AtomicUpdate, puts it on `update_queue`
    and moves the file to `applied/`; a file that doesn't load stays where
    it is, with the reason shown. The interpreter thread's answers
    (`update_results`) and the moment a pending update is applied are shown
    as the latest message.
    """

    def __init__(self, inbox: UpdateInbox, vm: VirtualMachine, update_queue: queue.Queue,
                 update_results: queue.Queue, poll_interval: float = 0.5):
        self._inbox = inbox
        self._vm = vm
        self._update_queue = update_queue
        self._update_results = update_results
        self._poll_interval = poll_interval
        self._inbox_state = InboxState(file=None)
        self._checked_at = float("-inf")
        self._submitted: Optional[str] = None   # file name on its way to the VM, until its UpdateStatus
        self._pending: Optional[str] = None     # file name pending in the VM, until applied
        self._last_message: Optional[str] = None

    def state(self) -> LiveUpdateState:
        self._take_results()
        if self._pending is not None and not self._vm.has_pending_update():
            self._last_message = f"{self._pending} applied"
            self._pending = None
        if time.monotonic() - self._checked_at >= self._poll_interval:
            self._inbox_state = self._inbox.state()
            self._checked_at = time.monotonic()

        messages = []
        if self._pending is not None or self._submitted is not None:
            messages.append(WAITING_MESSAGE)
        if self._inbox_state.message:
            messages.append(self._inbox_state.message)
        if self._last_message:
            messages.append(self._last_message)

        if self._pending is not None or self._submitted is not None:
            label, enabled = f"Update pending: {self._pending or self._submitted}", False
        elif self._inbox_state.ready:
            label, enabled = f"Submit update: {os.path.basename(self._inbox_state.file)}", True
        elif self._inbox_state.message:   # e.g. more than one file
            label, enabled = "One update file at a time", False
        else:
            label, enabled = f"No update file in {os.path.basename(self._inbox.folder)}/", False
        return LiveUpdateState(label, enabled, tuple(messages))

    def submit(self) -> None:
        self._inbox_state = self._inbox.state()   # the folder may have changed since the last check
        self._checked_at = time.monotonic()
        if not self._inbox_state.ready or self._submitted is not None or self._vm.has_pending_update():
            return
        path = self._inbox_state.file
        name = os.path.basename(path)
        try:
            update = self._inbox.load(path)
        except UpdateFileError as error:
            self._last_message = f"Not submitted, {error} (the file stays in {os.path.basename(self._inbox.folder)}/)"
            print(self._last_message)
            return
        self._update_queue.put(SubmittedUpdate(name, update))
        self._inbox.mark_applied(path)
        self._submitted = name
        self._last_message = f"{name} submitted"
        self._inbox_state = self._inbox.state()

    def _take_results(self) -> None:
        while True:
            try:
                status = self._update_results.get_nowait()
            except queue.Empty:
                return
            if status.name == self._submitted:
                self._submitted = None
            if status.kind == "submitted":
                self._pending = status.name
                self._last_message = f"{status.name} submitted"
            else:
                self._last_message = f"{status.name} rejected: {status.message}"

def _apply_queued_commands(channel: ThreadChannel, model: BaseSimulationModel) -> None:
    """Simulation thread: applies what the interpreter queued, in this order:
    startup instantiations (so a part created now exists for what follows),
    live update batches (one list of ModelUpdateCommands per flush, applied
    in order: added parts first, then new configured values; each command
    calls its own operation on the model, see synchronization.py), actions.
    """
    while not channel.instantiate_queue.empty():
        command = channel.instantiate_queue.get_nowait()
        model.instantiate_part(command.qualified_name, command.part_def_name, command.attrs)

    while not channel.model_update_queue.empty():
        for command in channel.model_update_queue.get_nowait():
            command.accept(model)

    while not channel.action_queue.empty():
        command = channel.action_queue.get_nowait()
        model.execute_action(command.qualified_name, command.action_name, command.args)

def _wait_for_go(channel: ThreadChannel, frame: int, interpreter_thread: threading.Thread) -> None:
    """Simulation thread, lockstep (design doc, Topic 10): asks "may I move
    past `frame`?" and blocks until the interpreter's "go" for that frame,
    sent at the start of the round after the one that took the question
    (normally one round, a few milliseconds).

    Waits in 0.1 s slices and raises if the interpreter thread has ended
    meanwhile (e.g. an exception in an update's apply()), instead of
    freezing the window; raises if the answer is for another frame.
    """
    channel.move_request_queue.put(frame)
    while True:
        try:
            answer = channel.move_permission_queue.get(timeout=0.1)
        except queue.Empty:
            if not interpreter_thread.is_alive():
                raise RuntimeError(f"The interpreter thread ended while the simulation waited "
                                   f"for permission to move past frame {frame}")
            continue
        if answer != frame:
            raise RuntimeError(f"The simulation asked to move past frame {frame}, "
                               f"but got permission for frame {answer}")
        return

def run_interpreter_loop(vm: VirtualMachine, stop_event: threading.Event,
                          started_event: threading.Event, tick_delay: float,
                          update_queue: queue.Queue, update_results: queue.Queue) -> None:
    """
    The actual behaviour of the interpreter loop, which will live in the Background thread.
    Waits for `started_event` (set when the simulation visualization execute `on_start` method described in
    the `main` method), then does the model's one-time eager part-instantiation pass and repeatedly
    steps the VM until `stop_event` is set. Before each step, hands a queued update over to the VM
    (`_hand_over_update`).

    vm: LipVM virtual machine which will interpret the SysML model
    model: the actual simulation model class to be used
    stop_event: signals the loop to stop once set (e.g. when the visualization window closes)
    started_event: signals the interpreter thread to start, which is performed by the Main thread
    tick_delay: seconds to sleep between reactive passes
    update_queue: SubmittedUpdates from the window, to hand over to the VM
    update_results: where each one's UpdateStatus is reported back to the window
    """

    started_event.wait()
    if stop_event.is_set():
        return

    # vm.init() already enqueued an InstantiateCommand per Part described in
    # the SysML model (Namespace.evaluate() -> PartInstantiation.evaluate() ->
    # SimulationBridge.instantiate(), fire-and-forget); this first step starts
    # the first round. on_tick(), on the pygame thread, is what actually drains
    # these into `model` and prints each one as it happens -- this thread has no
    # way to know when that drain is done without adding new synchronization.
    vm.step()

    # Continue to execute LipVM virtual machine step until the stop signal is performed in the main thread
    while not stop_event.is_set():
        # No sleep while an update is pending: each round then waits for the
        # simulation's question in SynchronizationManager.start_round
        # (lockstep), so the window's frame rate paces the rounds instead.
        # Nor while the simulation waits for its "go" (answered at the next
        # round start): after an update is applied mid-round, sleeping before
        # each remaining step would keep the window frozen (measured ~125 ms).
        if not vm.has_pending_update() and not vm.state.synchronization_manager.simulation_waiting:
            time.sleep(tick_delay)
        _hand_over_update(vm, update_queue, update_results)
        vm.step()

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sysml", help=f"Path to the .sysml model to run")
    parser.add_argument("--tick-delay", type=float, default=0.02,
                         help="Seconds between interpreter reactive passes (default: 0.02)")
    parser.add_argument("--updates-dir", default=DEFAULT_UPDATES_DIR,
                        help="Folder watched for update files during the demo (default: updates/ next to this file)")
    parser.add_argument("--simulation-model", choices=sorted(REGISTERED_SIMULATION_MODELS),
                        help="Which simulation domain to run", required=True)
    args = parser.parse_args()

    model_class, visualization_class = REGISTERED_SIMULATION_MODELS[args.simulation_model]
    vm, model = build_simulation(args.sysml, model_class)
    # Lockstep while an update is pending (design doc, Topic 10): the
    # interpreter waits for the simulation's "may I move?" at each round
    # start. Set before the interpreter thread starts; the channel exists
    # since vm.init(). on_tick must ask whenever an update is pending,
    # otherwise the interpreter waits forever.
    vm.state.channel.lockstep_enabled = True

    stop_event = threading.Event()
    started_event = threading.Event()
    # Live updates: SubmittedUpdates from the window to the interpreter
    # thread, and their UpdateStatus back.
    update_queue: queue.Queue[SubmittedUpdate] = queue.Queue()
    update_results: queue.Queue[UpdateStatus] = queue.Queue()

    def on_start() -> None:
        """Start button's click handler. Just releases the interpreter
        thread -- must not block, since it runs inside the visualization's
        own event loop.
        """
        started_event.set()

    # Frame numbers for lockstep's questions (same idiom as Factory's token ids).
    frames = itertools.count(1)

    def on_tick() -> None:
        """Runs once per frame, after the model's own tick. Applies the
        queued commands (`_apply_queued_commands`), then publishes a fresh
        snapshot for the interpreter thread to read.

        While an update is pending (lockstep, design doc Topic 10): having
        published, asks the interpreter "may I move past this frame?" and
        waits for "go" (`_wait_for_go`), so the round that takes the
        question copies the values of a paused simulation; then applies
        what came with "go" (a live update's batch, actions), before the
        next `model.tick()`.

        `Namespace.evaluate()` (syntax.py) enqueues one InstantiateCommand
        per PartInstantiation, once, during `vm.init()`; live
        changes to a part's configured values arrive separately, on
        `model_update_queue`. `model.instantiate_machine()` stays a no-op
        for a qualified_name it already has.
        """
        frame = next(frames)
        channel: ThreadChannel = vm.state.channel

        _apply_queued_commands(channel, model)

        for item_name, source_qualified_name in model.drain_events():
            SimulationBridge.emit_event(channel, item_name, source_qualified_name)

        channel.latest_snapshot.publish(model.build_snapshot())

        if vm.has_pending_update():
            _wait_for_go(channel, frame, interpreter_thread)
            _apply_queued_commands(channel, model)

    interpreter_thread = threading.Thread(
        target=run_interpreter_loop,
        args=(vm, stop_event, started_event, args.tick_delay, update_queue, update_results),
        daemon=True,
    )
    interpreter_thread.start()

    try:
        live_update = LiveUpdateControl(UpdateInbox(args.updates_dir), vm, update_queue, update_results)
        visualization_class().run(model, on_start, on_tick,  # blocks on the main thread until the window closes
                                  live_update=live_update.state, on_submit_update=live_update.submit)
    finally:
        stop_event.set()
        started_event.set()  # release the interpreter thread if it's still waiting on "Start"
        interpreter_thread.join(timeout=2)


if __name__ == "__main__":
    main()
