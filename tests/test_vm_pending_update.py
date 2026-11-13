"""The VM's pending-update interface for live submission (design doc,
Language-Safe-and-Execution-Tranquility-points.md, Topic 10 "Lockstep while an
update is pending"):

- `VirtualMachine.has_pending_update()`: whether an update waits to be applied;
- `VirtualMachine.submit(update, HOTSWAP)`: hand an update over between two
  steps, without `update()`'s `stop()`/`run()`;
- `RuntimeState.has_pending_update()`: the same answer, reachable by language
  code, which only receives the runtime state.

Language-independent, so a minimal test-only language is used.
"""

import pytest
from pyecore.ecore import MetaEClass

from core.edit import EditScript, Update
from core.language import AbstractSyntaxElement, RuntimeState, Scenario
from core.operation import Operation
from core.vm import ProgramUpdateOption, VirtualMachine

HOTSWAP = ProgramUpdateOption.HOTSWAP


# --- Helpers: a minimal language, just enough for vm.init() ---

class _Program(AbstractSyntaxElement, metaclass=MetaEClass):
    """A program that does nothing when run."""

    def evaluate(self, runtime: RuntimeState) -> Operation:
        return Operation(lambda: None)


class _RecordingEditScript(EditScript):
    """Records which syntax it was attached to, instead of visiting it."""

    def attach_to(self, syntax: AbstractSyntaxElement) -> None:
        self.attached_to = syntax


def _initialized_vm() -> VirtualMachine:
    vm = VirtualMachine()
    vm.scenario = Scenario(program_definition=_Program(identifier=0))
    vm.init()
    return vm


# --- VirtualMachine.has_pending_update ---

def test_no_pending_update_after_construction():
    assert VirtualMachine().has_pending_update() is False


def test_pending_update_is_reported():
    # Given: an update waiting to be applied
    vm = VirtualMachine()
    vm._pending_update = Update()

    # Then: the VM reports it
    assert vm.has_pending_update() is True


# --- VirtualMachine.submit ---

def test_submit_makes_the_update_pending_without_running():
    # Given: a VM with nothing pending
    vm = _initialized_vm()
    update = Update()

    # When: an update is submitted
    vm.submit(update, HOTSWAP)

    # Then: it is pending, and the VM didn't start running (unlike update())
    assert vm._pending_update is update
    assert vm.running is False


def test_submit_attaches_the_edit_script_to_the_scenario():
    # Given: an update that edits the syntax
    vm = _initialized_vm()
    edit_script = _RecordingEditScript()

    # When: it is submitted
    vm.submit(Update(edit_script=edit_script), HOTSWAP)

    # Then: its edit script is attached to the running program, as update() does
    assert edit_script.attached_to is vm.scenario


def test_submit_rejects_restart():
    # Given: a VM with nothing pending, and an update that edits the syntax
    vm = _initialized_vm()
    edit_script = _RecordingEditScript()

    # When / Then: RESTART is refused (it belongs to update())
    with pytest.raises(ValueError):
        vm.submit(Update(edit_script=edit_script), ProgramUpdateOption.RESTART)

    # And: nothing changed
    assert vm._pending_update is None
    assert not hasattr(edit_script, "attached_to")


def test_submit_raises_if_an_update_is_already_pending():
    # Given: an update already pending
    vm = _initialized_vm()
    first = Update()
    vm.submit(first, HOTSWAP)
    second_edit_script = _RecordingEditScript()

    # When / Then: a second submission is refused instead of replacing it
    with pytest.raises(RuntimeError):
        vm.submit(Update(edit_script=second_edit_script), HOTSWAP)

    # And: nothing changed, the first update is not lost
    assert vm._pending_update is first
    assert not hasattr(second_edit_script, "attached_to")


# --- RuntimeState.has_pending_update ---

def test_runtime_reports_the_vms_pending_update():
    # Given: the runtime state the VM created
    vm = _initialized_vm()
    assert vm.state.has_pending_update() is False

    # When / Then: it follows the VM's pending update live, without re-init
    vm._pending_update = Update()
    assert vm.state.has_pending_update() is True

    vm._pending_update = None
    assert vm.state.has_pending_update() is False


def test_runtime_state_without_a_vm_raises():
    # A runtime state built by hand (as some tests do) has no VM to ask
    with pytest.raises(RuntimeError):
        RuntimeState().has_pending_update()
