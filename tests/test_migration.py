import pytest
from pyecore.ecore import EReference, MetaEClass

from core.edit import EditScript, DeleteSyntaxOperation, Update
from core.language import (
    AbstractSyntaxElement,
    UpdatePoint,
    UpdateBeforePoint,
    UpdateAfterPoint,
    RuntimeState,
)
from core.operation import Operation
from core.vm import VirtualMachine

from languages.robot.runtime import Direction, GridPosition, Maze, Robot


# --- Helpers: a minimal language whose command nodes are update points ---

class _Checkpoint(UpdateBeforePoint, metaclass=MetaEClass):
    """A command node a language engineer marked as a "before" checkpoint."""
    pass


class _AfterCheckpoint(UpdateAfterPoint, metaclass=MetaEClass):
    """A command node marked as an "after" checkpoint."""
    pass


class _OtherBefore(UpdateBeforePoint, metaclass=MetaEClass):
    """A "before" checkpoint of a different type than _Checkpoint."""
    pass


class _PlainNode(AbstractSyntaxElement, metaclass=MetaEClass):
    """A command node that is not a checkpoint at all."""
    pass


class _Program(AbstractSyntaxElement, metaclass=MetaEClass):
    commands = EReference(eType=AbstractSyntaxElement, upper=-1, containment=True)


class _FaceEast(Update):
    """Deletes the command at `index` under node `parent_identifier` and
    migrates the live robot to face east, at a _Checkpoint (before-point).

    A language engineer's Update owns its own edit script: it is built from
    the target node identifiers in the constructor, not supplied per call.
    """

    def __init__(self, parent_identifier: int, index: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.edit_script = EditScript(
            operations=[DeleteSyntaxOperation(identifier=parent_identifier, index=index)]
        )

    def checkpoint_type(self) -> type:
        return _Checkpoint

    def apply(self, runtime: RuntimeState) -> None:
        runtime.maze.robot.direction = Direction.EAST


class _FaceEastAfter(_FaceEast):
    """Same, but applied at an _AfterCheckpoint (after-point)."""

    def checkpoint_type(self) -> type:
        return _AfterCheckpoint


class _NeverReady(_FaceEast):
    def condition(self, runtime: RuntimeState) -> bool:
        return False


def _make_runtime() -> RuntimeState:
    robot = Robot(name="robot", position=GridPosition(column=0, row=0), direction=Direction.NORTH)
    maze = Maze(name="maze", width=5, height=1, robot=robot)
    return RuntimeState(elements=[maze])


def _pending_vm(update: Update, program: _Program, current_node: AbstractSyntaxElement) -> VirtualMachine:
    if update.edit_script is not None:
        update.edit_script.attach_to(program)
    vm = VirtualMachine()
    vm._pending_update = update
    vm._runtime = _make_runtime()
    vm._operation = Operation(lambda: None, args=(current_node, vm._runtime))
    return vm


# --- Checkpoint marking ---

def test_plain_node_is_not_an_update_point():
    assert _PlainNode(identifier=1).isUpdatePoint() is False


def test_checkpoint_node_is_an_update_point():
    node = _Checkpoint(identifier=1)
    assert node.isUpdatePoint() is True
    assert node.isUpdateBefore() is True
    assert node.isUpdateAfter() is False


def test_update_point_before_after_are_abstract():
    node = UpdatePoint(identifier=1)
    assert node.isUpdatePoint() is True
    with pytest.raises(NotImplementedError):
        node.isUpdateBefore()


# --- Update defaults ---

def test_update_condition_defaults_to_true_and_apply_is_noop():
    update = Update()
    assert update.condition(_make_runtime()) is True
    update.apply(_make_runtime())  # no-op, does not raise


def test_update_requires_a_checkpoint_type():
    with pytest.raises(NotImplementedError):
        Update().checkpoint_type()


# --- VM applies the update at a matching checkpoint ---

def test_before_update_applied_before_its_node_runs():
    # Given: a program whose commands are "before" checkpoints
    first = _Checkpoint(identifier=1)
    program = _Program(identifier=0, commands=[first, _Checkpoint(identifier=2)])

    update = _FaceEast(parent_identifier=0, index=1)
    vm = _pending_vm(update, program, current_node=first)

    # When: the pre-execution check reaches the matching before-checkpoint
    vm._apply_pending_update(before=True)

    # Then: the edit is applied and the migration ran
    assert vm._pending_update is None
    assert [cmd.identifier for cmd in program.commands] == [1]
    assert vm._runtime.maze.robot.direction == Direction.EAST


def test_before_update_not_applied_after_its_node_runs():
    # Given: a before-checkpoint update
    first = _Checkpoint(identifier=1)
    program = _Program(identifier=0, commands=[first, _Checkpoint(identifier=2)])

    update = _FaceEast(parent_identifier=0, index=1)
    vm = _pending_vm(update, program, current_node=first)

    # When: only the post-execution check runs
    vm._apply_pending_update(before=False)

    # Then: a before-point update is not taken into account after the node
    assert vm._pending_update is update
    assert [cmd.identifier for cmd in program.commands] == [1, 2]
    assert vm._runtime.maze.robot.direction == Direction.NORTH


def test_after_update_applied_only_after_its_node_runs():
    # Given: a program whose commands are "after" checkpoints
    first = _AfterCheckpoint(identifier=1)
    program = _Program(identifier=0, commands=[first, _AfterCheckpoint(identifier=2)])

    update = _FaceEastAfter(parent_identifier=0, index=1)
    vm = _pending_vm(update, program, current_node=first)

    # When: the pre-execution check runs -- too early for an after-point
    vm._apply_pending_update(before=True)

    # Then: still pending
    assert vm._pending_update is update
    assert [cmd.identifier for cmd in program.commands] == [1, 2]

    # When: the post-execution check runs
    vm._apply_pending_update(before=False)

    # Then: now applied
    assert vm._pending_update is None
    assert [cmd.identifier for cmd in program.commands] == [1]
    assert vm._runtime.maze.robot.direction == Direction.EAST


def test_update_waits_when_node_type_does_not_match():
    # Given: the running node is a checkpoint of the *wrong* type (same timing)
    node = _OtherBefore(identifier=1)
    program = _Program(identifier=0, commands=[node, _OtherBefore(identifier=2)])

    update = _FaceEast(parent_identifier=0, index=1)
    vm = _pending_vm(update, program, current_node=node)

    # When
    vm._apply_pending_update(before=True)

    # Then: nothing applied, update still pending
    assert vm._pending_update is update
    assert [cmd.identifier for cmd in program.commands] == [1, 2]
    assert vm._runtime.maze.robot.direction == Direction.NORTH


def test_update_waits_when_node_is_not_a_checkpoint():
    # Given: the running node is not an update point at all
    node = _PlainNode(identifier=1)
    program = _Program(identifier=0, commands=[node, _PlainNode(identifier=2)])

    update = _FaceEast(parent_identifier=0, index=1)
    vm = _pending_vm(update, program, current_node=node)

    # When
    vm._apply_pending_update(before=True)

    # Then
    assert vm._pending_update is update
    assert [cmd.identifier for cmd in program.commands] == [1, 2]


def test_update_waits_when_condition_is_false():
    # Given: matching checkpoint, but the update's condition never holds
    first = _Checkpoint(identifier=1)
    program = _Program(identifier=0, commands=[first, _Checkpoint(identifier=2)])

    update = _NeverReady(parent_identifier=0, index=1)
    vm = _pending_vm(update, program, current_node=first)

    # When
    vm._apply_pending_update(before=True)

    # Then: held back until the condition holds
    assert vm._pending_update is update
    assert [cmd.identifier for cmd in program.commands] == [1, 2]
    assert vm._runtime.maze.robot.direction == Direction.NORTH


def test_update_skips_glue_operations_without_a_syntax_node():
    # Given: a glue operation carrying no AbstractSyntaxElement in its args
    program = _Program(identifier=0, commands=[_Checkpoint(identifier=1)])

    update = _FaceEast(parent_identifier=0, index=0)
    if update.edit_script is not None:
        update.edit_script.attach_to(program)
    vm = VirtualMachine()
    vm._pending_update = update
    vm._runtime = _make_runtime()
    vm._operation = Operation(lambda: None)

    # When
    vm._apply_pending_update(before=True)

    # Then: nothing crashes, update stays pending
    assert vm._pending_update is update
    assert [cmd.identifier for cmd in program.commands] == [1]
