from core.edit import EditScript, InsertSyntaxOperation, DeleteSyntaxOperation 

from languages.robot.syntax import (
    Program,
    TurnRight,
    MoveForward,
    IfDoElse,
    IfCondition,
    RelativeDirection,
)

def test_attach_to_sets_edit_operation_on_nested_children():
    target = MoveForward(identifier=1)
    program = Program(commands=[
        IfDoElse(
            condition=IfCondition(direction=RelativeDirection.FRONT),
            doBody=[target],
            elseBody=[TurnRight()],
        ),
    ])

    operation = DeleteSyntaxOperation(identifier=1, index=0)
    edit_script = EditScript(operations=[operation])

    edit_script.attach_to(program)

    assert list(target.edit_operations) == [operation]


def test_insert_syntax_operation_apply_adds_element():
    program = Program(identifier=0, commands=[TurnRight(identifier=1)])
    new_command = MoveForward(identifier=2)

    operation = InsertSyntaxOperation(identifier=0, index=1, element=new_command)
    operation.apply(program)

    assert list(program.commands) == [program.commands[0], new_command]
    assert program.commands[1] is new_command


def test_delete_syntax_operation_apply_removes_child():
    first = TurnRight()
    second = MoveForward()
    program = Program(commands=[first, second])

    operation = DeleteSyntaxOperation(identifier=0, index=0)
    operation.apply(program)

    assert list(program.commands) == [second]
