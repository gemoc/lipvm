"""Interim driver for running a SysML v2 simulation model to completion.

`VirtualMachine.run()` only steps `Namespace.evaluate()`'s `Operation` — the
eager `visit()` walk that builds the `SysmlRuntimeState` registry. It never
touches any `ExecutableStateUsage`; running one is left to whoever calls
`usage.evaluate(runtime)` directly (see tests/test_sysmlv2.py). This module
is that caller, just looped instead of hand-driven per assertion.

Deliberately adds nothing to core.vm/core.operation: each tick is a plain
Python call to `ExecutableStateUsage.evaluate()`, same contract the tests
already rely on. Folding this into the VM's own Operation chain (making
ExecutableStateUsage/Transition real @operation links) is a separate,
larger refactor — see TODO-LIST.md.

Note this loop only supplies repetition; it never itself injects anything
into a usage's `pending` mailbox (TODO-LIST.md item 6 — still an external
concern), so a model with no other pending-producer will run its entry
prologue once and then idle every following tick.
"""

import argparse
import time

from core.language import Scenario
from core.vm import VirtualMachine
from tools.load_xmi_with_syntax import load

DEFAULT_MODEL = "tests/test_sysmlv2-simple.xmi"


def build_vm(xmi_path: str) -> VirtualMachine:
    """Loads `xmi_path` and runs the VM once to build the SysmlRuntimeState
    registry. Returns the VM, ready for `run_reactive_loop()`.
    """
    resource = load(xmi_path)
    scenario = Scenario(program_definition=resource.contents[0])

    vm = VirtualMachine()
    vm.scenario = scenario
    vm.init()
    vm.run()
    return vm


def executable_state_usages(vm: VirtualMachine):
    return [record.element_type
            for record in vm.state.sysml.lookup_table_executable_state_usages.records]


def run_reactive_loop(vm: VirtualMachine, tick_delay: float = 0.5, max_ticks: int | None = None) -> None:
    """Repeatedly re-evaluates every registered ExecutableStateUsage, one
    reactive pass each, until `vm.stop()` is called or `max_ticks` is
    reached. `vm.running` is already True after `build_vm()` (`run()` sets
    it and never resets it), so it doubles as this loop's own gate.
    """
    usages = executable_state_usages(vm)
    if not usages:
        print("No ExecutableStateUsage found in this model; nothing to run.")
        return

    print(f"Running {len(usages)} state usage(s): "
          f"{[usage.qualified_name for usage in usages]}")

    tick = 0
    try:
        while vm.running:
            for usage in usages:
                usage.evaluate(vm.state)
            tick += 1
            if max_ticks is not None and tick >= max_ticks:
                vm.stop()
                break
            time.sleep(tick_delay)
    except KeyboardInterrupt:
        vm.stop()
        print("\nStopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xmi", nargs="?", default=DEFAULT_MODEL,
                         help=f"Path to the .xmi model to run (default: {DEFAULT_MODEL})")
    parser.add_argument("--tick-delay", type=float, default=0.5,
                         help="Seconds to sleep between reactive passes (default: 0.5)")
    parser.add_argument("--max-ticks", type=int, default=None,
                         help="Stop after this many reactive passes (default: run until Ctrl+C)")
    args = parser.parse_args()

    vm = build_vm(args.xmi)
    run_reactive_loop(vm, tick_delay=args.tick_delay, max_ticks=args.max_ticks)


if __name__ == "__main__":
    main()
