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
import threading
import time

from core.language import Scenario
from core.vm import VirtualMachine
from languages.sysmlv2.simulation_models.facade_proxy import SimulationBridge, ThreadChannel
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import FischertechnikVisualization
from languages.sysmlv2.simulation_models.generic import BaseSimulationModel, SimulationVisualization
from tools.load_xmi_with_syntax import load

# A Dict describing what Simulation Model and Visualization is ready to be used as part of this CLI
REGISTERED_SIMULATION_MODELS: dict[str, tuple[type[BaseSimulationModel], type[SimulationVisualization]]] = {
    "fischertechnik": (Factory, FischertechnikVisualization),
}

def build_simulation(xmi_path: str, simulation_model_class: type[BaseSimulationModel]) -> tuple[VirtualMachine, BaseSimulationModel]:
    """Loads the SysML model (represented by `xmi_path), constructs a fresh instance of `BaseSimulationModel`,
    and a fresh LipVM virtual machine. Deliberately doesn't step the virtual machine, it waits until it is started
    through the Main thread (Simulation Visualization thread).

    xmi_path: Path to the SysML model to be loaded (format .xmi)
    simulation_model_class: the actual simulation model class to be used
    """
    resource = load(xmi_path)
    scenario = Scenario(program_definition=resource.contents[0])

    vm = VirtualMachine()
    vm.scenario = scenario
    vm.init()

    model = simulation_model_class()

    return vm, model

def run_interpreter_loop(vm: VirtualMachine, stop_event: threading.Event,
                          started_event: threading.Event, tick_delay: float) -> None:
    """
    The actual behaviour of the interpreter loop, which will live in the Background thread.
    Waits for `started_event` (set when the simulation visualization execute `on_start` method described in
    the `main` method), then does the model's one-time eager part-instantiation pass and repeatedly
    steps the VM until `stop_event` is set.

    vm: LipVM virtual machine which will interpret the SysML model
    model: the actual simulation model class to be used
    stop_event: signals the loop to stop once set (e.g. when the visualization window closes)
    started_event: signals the interpreter thread to start, which is performed by the Main thread
    tick_delay: seconds to sleep between reactive passes
    """

    started_event.wait()
    if stop_event.is_set():
        return

    # First step: enqueues an InstantiateCommand per Part described in the SysML
    # model (PartInstantiation.evaluate() -> SimulationBridge.instantiate(),
    # fire-and-forget). on_tick(), on the pygame thread, is what actually drains
    # these into `model` and prints each one as it happens -- this thread has no
    # way to know when that drain is done without adding new synchronization.
    vm.step()

    # Continue to execute LipVM virtual machine step until the stop signal is performed in the main thread
    while not stop_event.is_set():
        time.sleep(tick_delay)
        vm.step()

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xmi", help=f"Path to the .xmi model to run")
    parser.add_argument("--tick-delay", type=float, default=0.25,
                         help="Seconds between interpreter reactive passes (default: 0.25)")
    parser.add_argument("--simulation-model", choices=sorted(REGISTERED_SIMULATION_MODELS),
                        help="Which simulation domain to run", required=True)
    args = parser.parse_args()

    model_class, visualization_class = REGISTERED_SIMULATION_MODELS[args.simulation_model]
    vm, model = build_simulation(args.xmi, model_class)

    stop_event = threading.Event()
    started_event = threading.Event()

    def on_start() -> None:
        """Start button's click handler. Just releases the interpreter
        thread -- must not block, since it runs inside the visualization's
        own event loop.
        """
        started_event.set()

    def on_tick() -> None:
        """Runs once per frame, after the model's own tick. Drains any
        queued instantiate/action commands and applies them (instantiate
        first, so a part created this call already exists for the
        action-drain and snapshot-publish steps that follow), then
        publishes a fresh snapshot for the interpreter thread to read.

        `read_events_and_execute()` (syntax.py) re-enqueues an
        InstantiateCommand for every PartInstantiation on every reactive
        tick, not just the first -- deliberately, so a part added later
        (e.g. a HOTSWAP edit) gets picked up rather than never. Repeats
        are idempotent on `model.instantiate_machine()`'s side (a no-op
        past the first call for a given qualified_name), but the "was
        this actually new" fact isn't visible from here without a
        Factory-specific query, and `model` is meant to stay any
        `BaseSimulationModel` -- so `already_printed` tracks it locally
        instead, printing each part exactly once regardless of how many
        more times its command gets redrained afterward.
        """

        channel: ThreadChannel = vm.state.channel

        while not channel.instantiate_queue.empty():
            command = channel.instantiate_queue.get_nowait()
            model.instantiate_machine(command.qualified_name, command.part_def_name, command.attrs)

        while not channel.action_queue.empty():
            command = channel.action_queue.get_nowait()
            model.execute_action(command.qualified_name, command.action_name, command.args)

        for item_name, source_qualified_name in model.drain_events():
            SimulationBridge.emit_event(channel, item_name, source_qualified_name)

        channel.latest_snapshot.publish(model.build_snapshot())

    interpreter_thread = threading.Thread(
        target=run_interpreter_loop, args=(vm, stop_event, started_event, args.tick_delay),
        daemon=True,
    )
    interpreter_thread.start()

    try:
        visualization_class().run(model, on_start, on_tick)  # blocks on the main thread until the window closes
    finally:
        stop_event.set()
        started_event.set()  # release the interpreter thread if it's still waiting on "Start"
        interpreter_thread.join(timeout=2)


if __name__ == "__main__":
    main()
