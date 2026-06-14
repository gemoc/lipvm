from core.vm import *
from languages.robot.runtime import *
from languages.robot.syntax import *


def test_program_initializes_maze_and_robot():

    # Given: a 3x3 maze, robot starting at (0,0) facing north, destination at (2,2)
    # and a wall at (1,1).
    program_syntax = ProgramInitializationDefinition(
        width=3,
        height=3,
        robot_position=GridPosition(column=0, row=0),
        destination_position=GridPosition(column=2, row=2),
        walls=[
            WallPosition(position=GridPosition(column=1, row=1)),
        ],
    )

    # A program that would route the robot from start to destination,
    # going around the wall.
    scenario_syntax = Program(commands=[
        TurnRight(),
        MoveForward(),
        MoveForward(),
        TurnRight(),
        MoveForward(),
        MoveForward(),
    ])

    vm = VirtualMachine()
    vm.scenario_syntax = scenario_syntax
    vm.program_syntax = program_syntax

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


def test_program_initializes_maze_with_if_conditions():

    # Given: a 5x1 maze, robot starting at (0,0) facing north, destination at (4,0).
    program_syntax = ProgramInitializationDefinition(
        width=5,
        height=1,
        robot_position=GridPosition(column=0, row=0),
        destination_position=GridPosition(column=4, row=0),
        walls=[],
    )

    # A program that turns east if the front cell is blocked, otherwise moves
    # forward, before navigating towards the destination.
    scenario_syntax = Program(commands=[
        IfDoElse(
            condition=IfCondition(direction=RelativeDirection.FRONT),
            doBody=[MoveForward()],
            elseBody=[TurnRight()],
        ),
        MoveForward(),
        MoveForward(),
        MoveForward(),
        MoveForward(),
    ])

    vm = VirtualMachine()
    vm.scenario_syntax = scenario_syntax
    vm.program_syntax = program_syntax

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

def test_program_initializes_maze_with_repeat_while():

    # Given: a 5x1 maze, robot starting at (0,0) facing north, destination at (4,0).
    program_syntax = ProgramInitializationDefinition(
        width=5,
        height=1,
        robot_position=GridPosition(column=0, row=0),
        destination_position=GridPosition(column=4, row=0),
        walls=[],
    )

    # A program that turns the robot east, then repeatedly moves it forward
    # until it reaches the destination.
    scenario_syntax = Program(commands=[
        TurnRight(),
        RepeatWhile(
            condition=ReachedDestinationCondition(),
            body=[MoveForward()],
        ),
    ])

    vm = VirtualMachine()
    vm.scenario_syntax = scenario_syntax
    vm.program_syntax = program_syntax

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


def test_update_program_replaces_repeat_while_with_if_condition():

    # Given: the same 5x1 maze as test_program_initializes_maze_with_repeat_while
    # (robot starting at (0,0) facing north, destination at (4,0)).
    program_syntax = ProgramInitializationDefinition(
        identifier=1,
        width=5,
        height=1,
        robot_position=GridPosition(column=0, row=0),
        destination_position=GridPosition(column=4, row=0),
        walls=[],
    )

    # A program that turns the robot east, then repeatedly moves it forward
    # until it reaches the destination.
    #
    # Every syntax element is given a different, non-default identifier so
    # that the edit script below only targets the "repeat while" command
    # (identifier generation will be addressed separately later).
    repeat_while = RepeatWhile(
        identifier=3,
        condition=ReachedDestinationCondition(identifier=4),
        body=[MoveForward(identifier=5)],
    )
    scenario_syntax = Program(
        identifier=6,
        commands=[
            TurnRight(identifier=2),
            repeat_while,
        ],
    )

    vm = VirtualMachine()
    vm.scenario_syntax = scenario_syntax
    vm.program_syntax = program_syntax

    # When: the virtual machine is run a first time.
    vm.init()
    vm.run()

    state = vm.state
    assert state.maze.width == 5
    assert state.maze.robot.position.column == 0
    assert state.maze.robot.position.row == 0
    assert vm.running

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
        DeleteSyntaxOperation(identifier=scenario_syntax.identifier, index=1),
        InsertSyntaxOperation(identifier=scenario_syntax.identifier, index=1, element=if_front_is_free),
    ])

    # When: the program is updated and the virtual machine is restarted from scratch.
    vm.udpate(edit_script, ProgramUpdateOption.RESTART)

    # Then: the edit operations have been attached to the syntax tree...
    assert list(scenario_syntax.edit_operations) == list(edit_script.operations)

    # ...and the virtual machine was reinitialized and re-run from its initial state.
    state = vm.state
    assert state.maze.width == 5
    assert state.maze.robot.position.column == 1
    assert state.maze.robot.position.row == 0
    assert state.maze.robot.direction == Direction.EAST
    assert vm.running
