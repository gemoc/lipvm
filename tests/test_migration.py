from pyecore.ecore import EAttribute, EInt, MetaEClass

from core.edit import EditScript, DeleteSyntaxOperation
from core.language import MigrationScript, RuntimeState, SafepointCondition
from core.operation import Operation
from core.vm import VirtualMachine

from languages.robot.runtime import Direction, GridPosition, Maze, Robot
from languages.robot.syntax import Program, MoveForward


# --- Helpers ---

class _ColumnAtLeast(SafepointCondition, metaclass=MetaEClass):
    threshold = EAttribute(eType=EInt)

    def evaluate(self, runtime: RuntimeState) -> bool:
        return runtime.maze.robot.position.column >= self.threshold


def _make_runtime(column: int) -> RuntimeState:
    robot = Robot(name="robot", position=GridPosition(column=column, row=0), direction=Direction.EAST)
    maze = Maze(name="maze", width=5, height=1, robot=robot)
    return RuntimeState(elements=[maze])


# --- Tests ---

def test_migration_scripts_are_dedicated_instances():
    # Given
    first = MoveForward(identifier=1)
    second = MoveForward(identifier=2)

    # Then: each instance gets its own default scripts, not a shared singleton
    assert isinstance(first.prepare_migration, MigrationScript)
    assert isinstance(first.perform_migration, MigrationScript)
    assert isinstance(first.safepoint_condition, SafepointCondition)

    assert first.prepare_migration is not second.prepare_migration
    assert first.perform_migration is not second.perform_migration
    assert first.safepoint_condition is not second.safepoint_condition


def test_is_safe_to_migrate_defaults_to_true():
    # Given
    node = MoveForward(identifier=1)

    # Then
    assert node.isSafeToMigrate(_make_runtime(column=0)) is True


def test_is_safe_to_migrate_uses_safepoint_condition():
    # Given
    node = MoveForward(identifier=1, safepoint_condition=_ColumnAtLeast(threshold=2))

    # Then
    assert node.isSafeToMigrate(_make_runtime(column=0)) is False
    assert node.isSafeToMigrate(_make_runtime(column=2)) is True


def test_pending_edits_wait_for_safepoint():
    # Given
    blocked = MoveForward(identifier=1, safepoint_condition=_ColumnAtLeast(threshold=2))
    free = MoveForward(identifier=2, safepoint_condition=_ColumnAtLeast(threshold=2))
    program = Program(identifier=0, commands=[blocked, free])

    edit_script = EditScript(operations=[DeleteSyntaxOperation(identifier=0, index=1)])
    edit_script.attach_to(program)

    vm = VirtualMachine()
    vm._edit_script = edit_script
    vm._runtime = _make_runtime(column=0)
    vm._operation = Operation(lambda: None, args=(blocked, vm._runtime,))

    # When: safepoint not yet reached
    vm._apply_pending_edits()

    # Then: edit is still pending
    assert vm._edit_script is edit_script
    assert [cmd.identifier for cmd in program.commands] == [1, 2]

    # When: safepoint reached
    vm._runtime = _make_runtime(column=2)
    vm._operation = Operation(lambda: None, args=(free, vm._runtime,))
    vm._apply_pending_edits()

    # Then: edit is applied
    assert vm._edit_script is None
    assert [cmd.identifier for cmd in program.commands] == [1]


def test_pending_edits_skip_glue_operations():
    # Given: a glue operation carries no AbstractSyntaxElement in its args
    program = Program(identifier=0, commands=[MoveForward(identifier=1)])

    edit_script = EditScript(operations=[DeleteSyntaxOperation(identifier=0, index=0)])
    edit_script.attach_to(program)

    vm = VirtualMachine()
    vm._edit_script = edit_script
    vm._runtime = _make_runtime(column=0)
    vm._operation = Operation(lambda: None)

    # When
    vm._apply_pending_edits()

    # Then: edit stays pending, nothing crashes
    assert vm._edit_script is edit_script
    assert [cmd.identifier for cmd in program.commands] == [1]
