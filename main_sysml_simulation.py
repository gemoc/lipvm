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

Note the reactive loop itself only supplies repetition; injecting into a
usage's `pending` mailbox (TODO-LIST.md item 6) is a separate, optional step
via `sync_pending_items()` / `--pending-file`. Without it, a model with no
other pending-producer will run its entry prologue once and then idle every
following tick.

`--pending-file` is a live interface, not a one-shot seed: every tick,
`sync_pending_items()` reads the whole file, injects each valid line's item
into the matching usage's `pending` mailbox in file order, and truncates the
file — so appending new lines to it while the simulation is running is how
you feed it further signals.
"""

import argparse
import logging
import time

from core.language import Scenario
from core.vm import VirtualMachine
from tools.load_xmi_with_syntax import load

logger = logging.getLogger(__name__)

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


def sync_pending_items(pending_file: str, item_defs_table, usages_by_name: dict) -> None:
    """Reads the whole of `pending_file` — one entry per line, formatted
    `<name-of-the-executable-state-usage>.<qualified-name-of-the-item-def>`
    (blank lines and lines starting with '#' ignored) — appends each
    resolved ItemDef to the named ExecutableStateUsage's `pending` mailbox
    in file order, then truncates the file.

    Meant to be called once per reactive-loop tick rather than once at
    startup: since every line present gets consumed and the file is emptied
    afterwards, a later scan only ever sees lines appended since the last
    one, which is what makes `pending_file` usable as a live interface
    while the simulation is running rather than a one-shot seed.

    The usage side is its plain declared `name` (e.g. "main"), not its
    qualified_name — qualified names use "::" as their separator, never ".",
    so splitting each line on the first "." unambiguously separates the two
    halves.

    A malformed or unresolvable line is logged and dropped rather than
    raised: this runs inside the long-lived reactive loop now, so one bad
    line appended later shouldn't take the whole simulation down.
    """
    with open(pending_file, encoding="utf-8") as f:
        content = f.read()

    if not content.strip():
        return

    for lineno, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "." not in line:
            logger.warning(
                "%s:%d: expected '<usage-name>.<item-def-qualified-name>', got %r — skipping",
                pending_file, lineno, raw_line)
            continue
        usage_name, item_qualified_name = line.split(".", 1)

        matching_usages = usages_by_name.get(usage_name)
        if not matching_usages:
            logger.warning(
                "%s:%d: unknown executable state usage '%s' — skipping",
                pending_file, lineno, usage_name)
            continue

        record = item_defs_table.get_reference(item_qualified_name)
        if record is None:
            logger.warning(
                "%s:%d: unknown item def '%s' — skipping",
                pending_file, lineno, item_qualified_name)
            continue

        for usage in matching_usages:
            usage.pending.append(record.element_type)

    with open(pending_file, "w", encoding="utf-8"):
        pass


def run_reactive_loop(vm: VirtualMachine, tick_delay: float = 0.5, max_ticks: int | None = None,
                       pending_file: str | None = None) -> None:
    """Repeatedly re-evaluates every registered ExecutableStateUsage, one
    reactive pass each, until `vm.stop()` is called or `max_ticks` is
    reached. `vm.running` is already True after `build_vm()` (`run()` sets
    it and never resets it), so it doubles as this loop's own gate.

    When `pending_file` is given, `sync_pending_items()` runs at the start
    of every tick, before the usages are evaluated, so anything appended to
    that file before a tick is visible to it.
    """
    usages = executable_state_usages(vm)
    if not usages:
        print("No ExecutableStateUsage found in this model; nothing to run.")
        return

    print(f"Running {len(usages)} state usage(s): "
          f"{[usage.qualified_name for usage in usages]}")

    usages_by_name = {}
    for usage in usages:
        usages_by_name.setdefault(usage.name, []).append(usage)
    item_defs_table = vm.state.sysml.lookup_table_item_defs

    tick = 0
    try:
        while vm.running:
            if pending_file is not None:
                sync_pending_items(pending_file, item_defs_table, usages_by_name)
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
    parser.add_argument("--tick-delay", type=float, default=0.25,
                         help="Seconds to sleep between reactive passes (default: 0.25)")
    parser.add_argument("--max-ticks", type=int, default=None,
                         help="Stop after this many reactive passes (default: run until Ctrl+C)")
    parser.add_argument("--pending-file", default=None,
                         help="Path to a file with one '<usage-name>.<item-def-qualified-name>' "
                              "entry per line. Scanned every tick: each valid line is injected "
                              "into the matching ExecutableStateUsage's `pending` mailbox and "
                              "the file is then truncated, so appending to it while the "
                              "simulation runs feeds it further signals")
    args = parser.parse_args()

    vm = build_vm(args.xmi)
    run_reactive_loop(vm, tick_delay=args.tick_delay, max_ticks=args.max_ticks,
                       pending_file=args.pending_file)


if __name__ == "__main__":
    main()
