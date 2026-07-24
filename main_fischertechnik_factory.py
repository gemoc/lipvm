"""First integrated version of the interpreter + factory visualization,
per OVERVIEW-TASKS.md task 5 / the "Question 1" home for this wiring raised
in URGENT-STEP1-SUBTASKS.md.

Loads a SysML v2 model, builds a real `Factory`/`FischertechnikBridge` from
it (so every `part` declared in the model -- e.g. `cb1` -- becomes a real,
model-placed `ConveyorBeltMachine`), then runs the two halves as separate
threads per the architecture decided in OVERVIEW-TASKS.md:

- Main thread: `draw_factory()` (pygame requires this).
- Background thread: the interpreter's reactive loop, re-evaluating every
  `ExecutableStateUsage` on a tick.

Deliberately incremental, not the full task 3-5 pipeline: `ActualAction`
dispatch (task 3) and guard evaluation (task 4) aren't wired yet, so the
model's own `do`/`accept when` behavior can't move a belt through the
interpreter yet -- only the pygame panel's manual buttons can, same as
`factory_simulation_demo.py`. This is safe to run as real threads today
specifically because nothing on the interpreter's reactive path touches
`Factory`/`ConveyorBeltMachine` until that dispatch exists (verified against
`tests/conveyor-belt-simulation.xmi`: its only guarded transitions use
`accept when`, which `_match_transition()` skips entirely -- no transition
ever fires, so no cross-thread access happens). Once task 3/4 land, the two
threads will need the request/response queue design from OVERVIEW-TASKS.md
task 5 instead of this direct sharing.
"""

import argparse
import threading
import time

from core.language import Scenario
from core.vm import VirtualMachine
from languages.sysmlv2.fischertechnik_bridge import FischertechnikBridge
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import draw_factory
from tools.load_xmi_with_syntax import load

DEFAULT_MODEL = "tests/conveyor-belt-simulation.xmi"


def build_simulation(xmi_path: str) -> tuple[VirtualMachine, Factory]:
    """Loads `xmi_path`, wires a fresh `Factory`/`FischertechnikBridge` onto
    the VM's runtime state, then runs one `vm.step()` -- enough to trigger
    `Namespace.evaluate()`'s eager part-instantiation pass (see
    URGENT-STEP1-SUBTASKS.md), which populates `factory` with a real,
    model-placed machine for every `part` usage in the model.

    The bridge must be set between `vm.init()` (which creates `vm.state`)
    and `vm.step()` (which is what actually runs the eager pass) -- it's
    read via `runtime.simulation_bridge` partway through that same step.
    """
    resource = load(xmi_path)
    scenario = Scenario(program_definition=resource.contents[0])

    vm = VirtualMachine()
    vm.scenario = scenario
    vm.init()

    factory = Factory()
    vm.state.simulation_bridge = FischertechnikBridge(factory)

    vm.step()

    return vm, factory


def executable_state_usages(vm: VirtualMachine):
    return [record.element_type
            for record in vm.state.sysml.lookup_table_executable_state_usages.records]


def run_interpreter_loop(vm: VirtualMachine, stop_event: threading.Event, tick_delay: float) -> None:
    """Repeatedly steps the VM until `stop_event` is set.

    `ExecutableStateUsage.evaluate()` is `@operation(is_step=True)` --
    calling it directly only builds an `Operation`, it doesn't run the body
    (see `core/operation.py`). The reactive pass is already wired into the
    VM's own operation chain by `Namespace.evaluate()` (its `lazy_while`
    over `read_events_and_execute`, `syntax.py:930-965`), so `vm.step()` is
    what actually drives it one reactive pass at a time -- same contract
    `test_simple_sysmlv2_example_with_behaviour` relies on. No behavior
    wired to the belt yet (see module docstring): today this just keeps the
    entry/default-transition prologue and (once implemented) signal-based
    transitions running independently of the render loop.
    """
    while not stop_event.is_set():
        vm.step()
        time.sleep(tick_delay)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xmi", nargs="?", default=DEFAULT_MODEL,
                         help=f"Path to the .xmi model to run (default: {DEFAULT_MODEL})")
    parser.add_argument("--tick-delay", type=float, default=0.25,
                         help="Seconds between interpreter reactive passes (default: 0.25)")
    args = parser.parse_args()

    vm, factory = build_simulation(args.xmi)

    print(f"Instantiated {len(factory.machines)} machine(s) from {args.xmi}:")
    for machine in factory.machines:
        print(f"  {machine.name} @ {machine.placementCoordinate}")

    stop_event = threading.Event()
    interpreter_thread = threading.Thread(
        target=run_interpreter_loop, args=(vm, stop_event, args.tick_delay), daemon=True,
    )
    interpreter_thread.start()

    try:
        draw_factory(factory)  # blocks on the main thread until the window closes
    finally:
        stop_event.set()
        interpreter_thread.join(timeout=2)


if __name__ == "__main__":
    main()
