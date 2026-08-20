"""Integrated interpreter + factory visualization, per OVERVIEW-TASKS.md
task 5 / the "Question 1" home for this wiring raised in
URGENT-STEP1-SUBTASKS.md.

Loads a SysML v2 model, builds a real `Factory`/`FischertechnikBridge` from
it (so every `part` declared in the model -- e.g. `cb1` -- becomes a real,
model-placed `ConveyorBeltMachine`), then runs the two halves as separate
threads per the architecture decided in OVERVIEW-TASKS.md:

- Main thread: `FactoryVisualization.run()` (pygame requires this).
- Background thread: the interpreter's reactive loop, re-evaluating every
  `ExecutableStateUsage` on a tick.

Guard evaluation (task 4) and real `ActualAction` dispatch (task 3) are
both wired up now, so the model's own `do`/`accept when` behavior genuinely
drives a belt through the interpreter, not just the pygame panel's manual
buttons.

Nothing runs until the user clicks "Start" in the visualization
(`on_start`, below): the model's eager
part-instantiation pass and the interpreter thread's reactive loop both
used to begin automatically, before the window was even shown; now both
wait for that explicit click, via `started_event`. `on_start` itself only
sets that event -- the eager pass runs on the interpreter thread, in
`run_interpreter_loop`, once released (see its docstring for why it can't
run synchronously inside `on_start` once the bridge is queue-backed). This
is a UX/timing fix, not a thread-safety one -- once "Start" is clicked,
this is still two threads directly sharing `Factory`/`ConveyorBeltMachine`
with no locking, now that the interpreter thread genuinely calls real
methods on it (`call_action`/`get_value_from_instance_attribute`). See
OVERVIEW-TASKS.md task 5 / URGENT-STEP1-SUBTASKS.md open question 1 for
the still-open cross-thread hazard this doesn't address -- the
request/response queue design (task 5, rest) is the actual fix, still not
built (see TODAYS-TASKS.md for the in-progress roadmap).
"""

import argparse
import threading
import time

from core.language import Scenario
from core.vm import VirtualMachine
from languages.sysmlv2.simulation_models.facade_proxy import ThreadChannel
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import FischertechnikVisualization
from tools.load_xmi_with_syntax import load

DEFAULT_MODEL = "tests/conveyor-belt-simulation.xmi"


def build_simulation(xmi_path: str) -> tuple[VirtualMachine, Factory]:
    """Loads `xmi_path` and wires a fresh `Factory`/`FischertechnikBridge`
    onto the VM's runtime state -- deliberately does NOT step the VM here.

    Also creates the `ThreadChannel` bundling everything the owning
    (pygame) thread and the interpreter thread use to communicate -- the
    snapshot `on_tick` publishes to and reads come from, and the action
    queue `on_tick` drains and calls come from -- returned alongside
    `factory` since `main()` needs it to wire up `on_tick`, same reason
    `factory` itself is returned.

    Stepping used to happen eagerly right here (one `vm.step()`, enough to
    trigger `Namespace.evaluate()`'s eager part-instantiation pass -- see
    URGENT-STEP1-SUBTASKS.md), before the visualization window was even
    shown. Now that both guard evaluation/firing (task 4) and real action
    dispatch (task 3) are wired up, the model can genuinely run on its own
    once started -- so "start" needs to be an explicit, visible user
    action from inside the visualization, not something that already
    happened silently by the time the window opens.

    The bridge exists as soon as `vm.init()` returns -- `Namespace.evaluate()`
    (`syntax.py`) constructs it eagerly now, no longer deferred behind a
    `vm.step()` call.
    """
    resource = load(xmi_path)
    scenario = Scenario(program_definition=resource.contents[0])

    vm = VirtualMachine()
    vm.scenario = scenario
    vm.init()

    factory = Factory()

    return vm, factory


def executable_state_usages(vm: VirtualMachine):
    return [record.element_type
            for record in vm.state.sysml.lookup_table_executable_state_usages.records]


def run_interpreter_loop(vm: VirtualMachine, factory: Factory, xmi_path: str, stop_event: threading.Event,
                          started_event: threading.Event, tick_delay: float) -> None:
    """Waits for `started_event` (set once the user clicks "Start" in the
    visualization) before stepping the VM at all, then repeatedly steps it
    until `stop_event` is set.

    Without this wait, this loop's own first `vm.step()` call would itself
    trigger the eager part-instantiation pass the instant this thread
    starts -- defeating the whole point of gating that behind a visible
    user action.

    This thread now does the model's one-time eager part-instantiation
    pass itself (the first `vm.step()` below), rather than main()'s
    `on_start` doing it synchronously on the pygame thread. That used to
    be safe because the bridge called into `Factory` directly; once the
    bridge is queue-backed (TODAYS-TASKS.md step 3+), `on_start` calling
    `vm.step()` from inside `FactoryVisualization.run()`'s own event-handling
    loop would deadlock -- it would block waiting for a reply that only
    that loop can produce, on a later iteration it can
    never reach while frozen inside this callback. Doing every `vm.step()`
    call from this one thread keeps a clean invariant: the interpreter
    thread is the only thread that ever calls into the bridge, full stop.

    `ExecutableStateUsage.evaluate()` is `@operation(is_step=True)` --
    calling it directly only builds an `Operation`, it doesn't run the body
    (see `core/operation.py`). The reactive pass is already wired into the
    VM's own operation chain by `Namespace.evaluate()` (its `lazy_while`
    over `read_events_and_execute`, `syntax.py:930-965`), so `vm.step()` is
    what actually drives it one reactive pass at a time -- same contract
    `test_simple_sysmlv2_example_with_behaviour` relies on.
    """
    started_event.wait()
    if stop_event.is_set():
        return

    # Calling vm.step() command the first time is mandatory since it
    # Signifies the instantiation of all the object. The subsequent vm.step()
    # will later focused on the executable state machine behaviour
    vm.step()
    print(f"Instantiated {len(factory.machines)} machine(s) from {xmi_path}:")
    for machine in factory.machines:
        print(f"  {machine.name} @ {machine.placementCoordinate}")

    while not stop_event.is_set():
        time.sleep(tick_delay)
        vm.step()

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xmi", nargs="?", default=DEFAULT_MODEL,
                         help=f"Path to the .xmi model to run (default: {DEFAULT_MODEL})")
    parser.add_argument("--tick-delay", type=float, default=0.25,
                         help="Seconds between interpreter reactive passes (default: 0.25)")
    args = parser.parse_args()

    vm, factory = build_simulation(args.xmi)

    stop_event = threading.Event()
    started_event = threading.Event()

    def on_start() -> None:
        """Runs on the main/pygame thread, from the "Start" button's click
        callback, synchronously inside `FactoryVisualization.run()`'s own
        event-handling loop -- so it must not itself call anything that
        blocks waiting on that same loop (see `run_interpreter_loop`'s
        docstring). Only releases the interpreter thread; the model's
        eager part-instantiation pass now happens there instead, once
        `started_event` is set.
        """
        started_event.set()

    interpreter_thread = threading.Thread(
        target=run_interpreter_loop, args=(vm, factory, args.xmi, stop_event, started_event, args.tick_delay),
        daemon=True,
    )
    interpreter_thread.start()

    def on_tick() -> None:
        """Runs on the main/pygame thread, right after `factory.tick()`
        each frame (see `FactoryVisualization.run()`) -- resolves this scenario's
        `ThreadChannel` (via the interpreter's own `simulation_bridge`,
        constructed inside `Namespace.evaluate()`, `syntax.py`) and
        perform the actual per-tick work

        One tick's worth of owning-thread work -- the only thread ever
        allowed to do any of the three things below (see HOMEWORK-SAYYID.md
        task 1 / facade_proxy.py's `SimulationSnapshot`/`ThreadChannel`
        docstrings). Order matters: instantiate first, so a part created this
        call already exists for the action-drain and snapshot-publish steps
        that follow it.

        1. Drains every `InstantiateCommand` queued since the last call and
           actually constructs/registers each one (`factory.instantiate_machine()`).
        2. Drains every `ActionCommand` queued since the last call and
           actually executes each one (`factory.execute_action()`) -- this is
           the one place any machine's action methods get called from, now
           that `SimulationBridge.call_action()` only ever enqueues.
        3. Publishes a fresh Factory-wide snapshot (`factory.build_snapshot()`,
           framework-agnostic, knows nothing about threads) so the interpreter
           thread's next attribute read sees this tick's state, not a stale
           or torn one.

        Deliberately a plain function taking `factory`/`channel` as arguments,
        not a closure over `main()`'s locals -- `on_tick()` below is the only
        caller that needs pygame/threading at all; anything driving one "tick"
        synchronously (e.g. a future test exercising real simulation behavior)
        can call this directly, no window or second thread required, since
        nothing here blocks (see TODAYS-TASKS.md).
        """

        channel: ThreadChannel = vm.state.simulation_bridge.channel

        while not channel.instantiate_queue.empty():
            command = channel.instantiate_queue.get_nowait()
            factory.instantiate_machine(command.qualified_name, command.part_def_name, command.attrs)

        while not channel.action_queue.empty():
            command = channel.action_queue.get_nowait()
            factory.execute_action(command.qualified_name, command.action_name, command.args)

        channel.latest_snapshot.publish(factory.build_snapshot())


    try:
        FischertechnikVisualization().run(factory, on_start, on_tick)  # blocks on the main thread until the window closes
    finally:
        stop_event.set()
        started_event.set()  # release the interpreter thread if it's still waiting on "Start"
        interpreter_thread.join(timeout=2)


if __name__ == "__main__":
    main()
