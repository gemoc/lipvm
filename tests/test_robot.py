from core.vm import *
from core.language import Scenario
from languages.robot.runtime import *
from languages.robot.syntax import *


def test_program_with_simple_commands():
    # Given a 3x3 maze, robot starting at (0,0) facing north, 
    # destination at (2,2) and a wall at (1,1).
    scenario = Scenario(
        program_definition=ProgramInitializationDefinition(
            width=3,
            height=3,
            robot_position=GridPosition(column=0, row=0),
            destination_position=GridPosition(column=2, row=2),
            walls=[
                WallPosition(position=GridPosition(column=1, row=1)),
            ],
        ),
        program_command=Program(commands=[
            TurnRight(),
            MoveForward(),
            MoveForward(),
            TurnRight(),
            MoveForward(),
            MoveForward(),
        ]),
    )

    vm = VirtualMachine()
    vm.scenario = scenario

    # When
    vm.init()
    vm.run()

    # Then
    state = vm.state
    maze = state.maze
    robot = maze.robot

    assert maze.width == 3
    assert maze.height == 3

    assert maze.start.column == 0
    assert maze.start.row == 0

    assert maze.destination.column == 2
    assert maze.destination.row == 2

    assert robot.position.column == 2
    assert robot.position.row == 2
    assert robot.direction == Direction.SOUTH

    assert maze.getCellAt(1, 1).isWallCell()
    assert maze.getCellAt(0, 0).isEmptyCell()


def test_program_with_if_condition():
    # Given a 5x1 maze, robot starting at (0,0) facing north, destination at (4,0).
    scenario = Scenario(
        program_definition=ProgramInitializationDefinition(
            width=5,
            height=1,
            robot_position=GridPosition(column=0, row=0),
            destination_position=GridPosition(column=4, row=0),
            walls=[],
        ),
        program_command=Program(commands=[
            IfDoElse(
                condition=IfCondition(direction=RelativeDirection.FRONT),
                doBody=[MoveForward()],
                elseBody=[TurnRight()],
            ),
            MoveForward(),
            MoveForward(),
            MoveForward(),
            MoveForward(),
        ]),
    )

    vm = VirtualMachine()
    vm.scenario = scenario

    # When
    vm.init()
    vm.run()

    # Then
    state = vm.state
    maze = state.maze
    robot = maze.robot

    assert maze.width == 5
    assert maze.height == 1

    assert maze.destination.column == 4
    assert maze.destination.row == 0

    assert robot.position.column == 4
    assert robot.position.row == 0
    assert robot.direction == Direction.EAST


def test_program_with_repeat_while():
    # Given: a 5x1 maze, robot starting at (0,0) facing north, destination at (4,0).
    scenario = Scenario(
        program_definition=ProgramInitializationDefinition(
            width=5,
            height=1,
            robot_position=GridPosition(column=0, row=0),
            destination_position=GridPosition(column=4, row=0),
            walls=[],
        ),
        program_command=Program(commands=[
            TurnRight(),
            RepeatWhile(
                condition=ReachedDestinationCondition(),
                body=[MoveForward()],
            ),
        ]),
    )

    vm = VirtualMachine()
    vm.scenario = scenario

    # When
    vm.init()
    vm.run()

    # Then
    state = vm.state
    maze = state.maze
    robot = maze.robot

    assert maze.width == 5
    assert maze.height == 1

    assert maze.destination.column == 4
    assert maze.destination.row == 0

    assert robot.position.column == 0
    assert robot.position.row == 0
    assert robot.direction == Direction.EAST

    assert maze.getCellAt(4, 0).isEmptyCell()


def test_update_program_and_restart():
    # Given: the same 5x1 maze as previously.
    program_definition = ProgramInitializationDefinition(
        identifier=1,
        width=5,
        height=1,
        robot_position=GridPosition(column=0, row=0),
        destination_position=GridPosition(column=4, row=0),
        walls=[],
    )
    
    # The repeat while loop of the previous test
    repeat_while = RepeatWhile(
        identifier=3,
        condition=ReachedDestinationCondition(identifier=4),
        body=[MoveForward(identifier=5)],
    )
    program_command = Program(
        identifier=6,
        commands=[
            TurnRight(identifier=2),
            repeat_while,
        ],
    )

    scenario = Scenario(
        program_definition=program_definition,
        program_command=program_command,
    )

    vm = VirtualMachine()
    vm.scenario = scenario

    # The virtual machine is run a first time.
    vm.init()
    vm.run()

    origin_state = vm.state

    # An edit script that removes the "repeat while" loop and replaces it with
    # an "if the cell ahead is free, move forward" check. Instead of driving
    # all the way to the destination, the robot would now only advance a
    # single step.
    if_front_is_free = IfDoElse(
        identifier=7,
        condition=IfCondition(identifier=8, direction=RelativeDirection.FRONT),
        doBody=[MoveForward(identifier=9)],
        elseBody=[],
    )

    edit_script = EditScript(operations=[
        DeleteSyntaxOperation(identifier=program_command.identifier, index=1),
        InsertSyntaxOperation(identifier=program_command.identifier, index=1, element=if_front_is_free),
    ])

    # When
    vm.udpate(edit_script, ProgramUpdateOption.RESTART)
    state = vm.state

    # Then
    assert origin_state.maze.width == 5
    assert origin_state.maze.robot.position.column == 0
    assert origin_state.maze.robot.position.row == 0

    assert all(operation.syntax is program_command for operation in edit_script.operations)
    
    assert state.maze.width == 5
    assert state.maze.robot.position.column == 1
    assert state.maze.robot.position.row == 0
    assert state.maze.robot.direction == Direction.EAST
    assert vm.running
