from core.edit import EditScript, InsertSyntaxOperation, UpdateSyntaxOperation, DeleteSyntaxOperation

from languages.robot.syntax import (
    Program,
    TurnRight,
    MoveForward,
    IfDoElse,
    IfCondition,
    RelativeDirection,
)


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


def test_edit_script_applies_all_operations():
    # Given
    program = Program(identifier=0, commands=[TurnRight(identifier=2), MoveForward(identifier=1)])
    edit_script = EditScript(operations=[DeleteSyntaxOperation(identifier=0, index=1)])
    edit_script.attach_to(program)

    # When
    edit_script.apply()

    # Then
    assert [cmd.identifier for cmd in program.commands] == [2]
