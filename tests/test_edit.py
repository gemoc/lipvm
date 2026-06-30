from pyecore.ecore import EAttribute, MetaEClass

from core.edit import EditScript, InsertSyntaxOperation, UpdateSyntaxOperation, DeleteSyntaxOperation
from core.language import MigrationScript, RuntimeState

from languages.robot.runtime import Direction, GridPosition, Maze, Robot
from languages.robot.syntax import (
    Program,
    TurnRight,
    MoveForward,
    IfDoElse,
    IfCondition,
    RelativeDirection,
)


# --- Helpers ---

class _SetRobotDirection(MigrationScript, metaclass=MetaEClass):
    direction = EAttribute(eType=Direction)

    def evaluate(self, runtime: RuntimeState) -> None:
        runtime.maze.robot.direction = self.direction


def _make_runtime() -> RuntimeState:
    robot = Robot(name="robot", position=GridPosition(column=0, row=0), direction=Direction.NORTH)
    maze = Maze(name="maze", width=5, height=1, robot=robot)
    return RuntimeState(elements=[maze])


# --- Tests ---

def test_attach_to_finds_nested_target_by_identifier():
    # Given
    target = MoveForward(identifier=1)
    program = Program(commands=[
        IfDoElse(
            condition=IfCondition(direction=RelativeDirection.FRONT),
            doBody=[target],
            elseBody=[TurnRight()],
        ),
    ])
    edit_op = DeleteSyntaxOperation(identifier=1, index=0)
    edit_script = EditScript(operations=[edit_op])

    # When
    edit_script.attach_to(program)

    # Then
    assert edit_op.syntax is target


def test_insert_adds_element_at_index():
    # Given
    program = Program(identifier=0, commands=[TurnRight(identifier=1)])
    new_command = MoveForward(identifier=2)
    edit_op = InsertSyntaxOperation(identifier=0, index=1, element=new_command, syntax=program)

    # When
    edit_op.apply()

    # Then
    assert list(program.commands) == [program.commands[0], new_command]
    assert program.commands[1] is new_command


def test_delete_removes_child_at_index():
    # Given
    first = TurnRight()
    second = MoveForward()
    program = Program(commands=[first, second])
    edit_op = DeleteSyntaxOperation(identifier=0, index=0, syntax=program)

    # When
    edit_op.apply()

    # Then
    assert list(program.commands) == [second]


def test_update_changes_attribute_value():
    # Given
    condition = IfCondition(identifier=1, direction=RelativeDirection.FRONT)
    edit_op = UpdateSyntaxOperation(
        identifier=1,
        attribute_name="direction",
        element=RelativeDirection.LEFT,
        syntax=condition,
    )

    # When
    edit_op.apply()

    # Then
    assert condition.direction == RelativeDirection.LEFT


def test_prepare_and_migrate_are_noop_without_migration_scripts():
    # Given
    program = Program(identifier=0, commands=[TurnRight(identifier=1)])
    edit_op = DeleteSyntaxOperation(identifier=0, index=0, syntax=program)

    # When / Then: no exception raised
    edit_op.prepare(RuntimeState())
    edit_op.migrate(RuntimeState())


def test_prepare_and_migrate_evaluate_migration_scripts():
    # Given
    runtime = _make_runtime()
    program = Program(
        identifier=0,
        commands=[TurnRight(identifier=1)],
        prepare_migration=_SetRobotDirection(direction=Direction.EAST),
        perform_migration=_SetRobotDirection(direction=Direction.SOUTH),
    )
    edit_op = DeleteSyntaxOperation(identifier=0, index=0, syntax=program)

    # When
    edit_op.prepare(runtime)

    # Then
    assert runtime.maze.robot.direction == Direction.EAST

    # When
    edit_op.migrate(runtime)

    # Then
    assert runtime.maze.robot.direction == Direction.SOUTH


def test_edit_script_prepare_apply_migrate_in_sequence():
    # Given
    program = Program(identifier=0, commands=[TurnRight(identifier=2), MoveForward(identifier=1)])
    edit_script = EditScript(operations=[DeleteSyntaxOperation(identifier=0, index=1)])
    edit_script.attach_to(program)

    # When
    edit_script.prepare(RuntimeState())
    edit_script.apply()
    edit_script.migrate(RuntimeState())

    # Then
    assert [cmd.identifier for cmd in program.commands] == [2]
