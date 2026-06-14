from pyecore.ecore import *

from core.language import AbstractSyntaxElement, RuntimeState
from core.operations import operation, loop, if_then_else

from languages.robot.runtime import (
    Direction,
    GridPosition,
    EmptyCell,
    WallCell,
    Robot,
    Maze,
)

# Relative direction for cell checks (relative to robot's current orientation)
RelativeDirection = EEnum("RelativeDirection")
RelativeDirection.eLiterals.append(EEnumLiteral("FRONT"))
RelativeDirection.eLiterals.append(EEnumLiteral("LEFT"))
RelativeDirection.eLiterals.append(EEnumLiteral("RIGHT"))

# Robot Commands
class Command(AbstractSyntaxElement, metaclass=MetaEClass):
    abstract = True

class TurnLeft(Command, metaclass=MetaEClass):
    
    @operation()
    def evaluate(self, runtime: RuntimeState) -> None:
        """Turn the robot 90 degrees to the left (counter-clockwise)."""
        robot = runtime.maze.robot
        match robot.direction:
            case Direction.NORTH:
                robot.direction = Direction.WEST
            case Direction.WEST:
                robot.direction = Direction.SOUTH
            case Direction.SOUTH:
                robot.direction = Direction.EAST
            case Direction.EAST:
                robot.direction = Direction.NORTH


class TurnRight(Command, metaclass=MetaEClass):

    @operation()
    def evaluate(self, runtime: RuntimeState) -> None:
        """Turn the robot 90 degrees to the right (clockwise)."""
        robot = runtime.maze.robot
        match robot.direction:
            case Direction.NORTH:
                robot.direction = Direction.EAST
            case Direction.EAST:
                robot.direction = Direction.SOUTH
            case Direction.SOUTH:
                robot.direction = Direction.WEST
            case Direction.WEST:
                robot.direction = Direction.NORTH


class MoveForward(Command, metaclass=MetaEClass):

    @operation()
    def evaluate(self, runtime: RuntimeState) -> None:
        """Move the robot one cell forward in its current direction.

        Raises:
            ValueError: If the target cell is a wall or out of bounds.
        """
        maze = runtime.maze
        robot = maze.robot
        deltaColumn = 0
        deltaRow = 0

        if robot.direction == Direction.EAST:
            deltaColumn = 1
        elif robot.direction == Direction.WEST:
            deltaColumn = -1

        if robot.direction == Direction.NORTH:
            deltaRow = -1
        elif robot.direction == Direction.SOUTH:
            deltaRow = 1

        targetColumn = robot.position.column + deltaColumn
        targetRow = robot.position.row + deltaRow

        try:
            targetCell = maze.getCellAt(targetColumn, targetRow)
            if targetCell.isWallCell():
                raise ValueError(
                    f"Robot cannot move forward: position ({targetColumn}, {targetRow}) is a wall"
                )
        except IndexError:
            raise ValueError(
                f"Robot cannot move forward: position ({targetColumn}, {targetRow}) is out of bounds"
            )

        # Move the robot
        robot.position.column = targetColumn
        robot.position.row = targetRow


class IfCondition(AbstractSyntaxElement, metaclass=MetaEClass):
    """A condition that checks if there's an empty cell in a relative direction from the robot's current position.

    The condition can only verify one of three relative directions:
      - FRONT: the cell directly ahead of the robot
      - LEFT: the cell to the left of the robot (90 degrees counter-clockwise)
      - RIGHT: the cell to the right of the robot (90 degrees clockwise)
    """

    direction = EAttribute(eType=RelativeDirection, lower=1, upper=1)

    @operation()
    def evaluate(self, runtime: RuntimeState) -> bool:
        """Evaluate whether the cell in the specified relative direction is empty.

        Returns True if the target cell exists and is empty, False otherwise
        (including out of bounds).
        """
        maze = runtime.maze
        robot = maze.robot
        deltaColumn = 0
        deltaRow = 0

        # Adjust offset based on the relative direction check
        match self.direction:
            case RelativeDirection.FRONT:
                if robot.direction == Direction.EAST:
                    deltaColumn = 1
                elif robot.direction == Direction.WEST:
                    deltaColumn = -1
                elif robot.direction == Direction.NORTH:
                    deltaRow = -1
                elif robot.direction == Direction.SOUTH:
                    deltaRow = 1
            case RelativeDirection.LEFT:
                if robot.direction == Direction.EAST:
                    deltaRow = -1
                elif robot.direction == Direction.WEST:
                    deltaRow = 1
                elif robot.direction == Direction.NORTH:
                    deltaColumn = -1
                elif robot.direction == Direction.SOUTH:
                    deltaColumn = 1
            case RelativeDirection.RIGHT:
                if robot.direction == Direction.EAST:
                    deltaRow = 1
                elif robot.direction == Direction.WEST:
                    deltaRow = -1
                elif robot.direction == Direction.NORTH:
                    deltaColumn = 1
                elif robot.direction == Direction.SOUTH:
                    deltaColumn = -1

        targetColumn = robot.position.column + deltaColumn
        targetRow = robot.position.row + deltaRow

        try:
            targetCell = maze.getCellAt(targetColumn, targetRow)
            return targetCell.isEmptyCell()
        except IndexError:
            return False


class IfDoElse(Command, metaclass=MetaEClass):
    """An if-do-else statement for the robot DSL.

    Evaluates a condition that checks if there's an empty cell relative to
    the robot's position. Executes either the doBody or elseBody commands
    based on the condition result. Both bodies can contain zero or more commands.
    """

    condition = EReference(eType=IfCondition, lower=1, upper=1, containment=False)
    doBody = EReference(eType=Command, lower=0, upper=-1, containment=True)
    elseBody = EReference(eType=Command, lower=0, upper=-1, containment=True)

    @operation(condition_result=lambda node, runtime: node.condition.evaluate(runtime))
    def evaluate(self, runtime: RuntimeState, condition_result: bool = None) -> None:
        """Evaluate the condition and execute the appropriate body.

        If the condition_result is True, evaluates the commands of doBody.
        If the condition_result is False, evaluates the commands of elseBody.
        """
        return if_then_else(condition_result, self.doBody, self.elseBody, lambda cmd: cmd.evaluate(runtime))

# Condition to check if robot has reached the destination
class ReachedDestinationCondition(AbstractSyntaxElement, metaclass=MetaEClass):
    """A condition that checks if the robot has reached the destination of the maze.

    Returns True if the robot's current position matches the destination position.
    """

    @operation()
    def evaluate(self, runtime: RuntimeState) -> bool:
        """Evaluate whether the robot's position matches the destination position.

        Returns True if the robot has reached the destination, False otherwise.
        """
        maze = runtime.maze
        robot = maze.robot
        return (
            robot.position.column == maze.destination.column
            and robot.position.row == maze.destination.row
        )

class RepeatWhile(Command, metaclass=MetaEClass):
    """A repeat-while statement for the robot DSL.

    Repeatedly evaluates all commands in the body as long as the condition is false.
    Once the condition becomes true, the loop terminates and execution continues.
    """

    condition = EReference(eType=ReachedDestinationCondition, lower=1, upper=1, containment=False)
    body = EReference(eType=Command, lower=0, upper=-1, containment=True)

    def evaluate(self, runtime: RuntimeState) -> None:
        """Evaluate the body commands repeatedly until the condition becomes true.

        Continues evaluating body commands as long as the condition is false.
        Once the condition returns True (robot reached destination), the loop stops.
        """
        return loop(self.body, lambda cmd: cmd.evaluate(runtime), self.condition.evaluate(runtime))


class WallPosition(Command, metaclass=MetaEClass):
    """Specifies the position of a wall cell in the maze."""
    position = EReference(eType=GridPosition, lower=1, upper=1)

# So that the language user can define a maze (as we would do with a state machine)
class ProgramInitializationDefinition(AbstractSyntaxElement, metaclass=MetaEClass):
    """Root element that groups all maze creation DSL statements.

    This is the main entry point from the user's DSL perspective. It collects
    dimensions, robot position, destination, and wall positions into a single
    configuration that can be used to build the actual Maze model.
    """
    width = EAttribute(eType=EInt)
    height = EAttribute(eType=EInt)

    robot_position = EReference(eType=GridPosition, lower=1, upper=1)
    destination_position = EReference(eType=GridPosition, lower=1, upper=1)

    walls = EReference(eType=WallPosition, lower=0, upper=-1)

    @operation()
    def evaluate(self, runtime: RuntimeState) -> None:
        """Populates the Maze runtime element with cells, positions for robot and destination, and wall cells."""

        runtime.maze.width = self.width
        runtime.maze.height = self.height

        # Set start position (robot starting point)
        runtime.maze.start = GridPosition(
            column=self.robot_position.column,
            row=self.robot_position.row
        )

        # Set destination position
        runtime.maze.destination = GridPosition(
            column=self.destination_position.column,
            row=self.destination_position.row
        )

        # Initialize the grid
        runtime.maze.cells = []
        for row in range(runtime.maze.height):
            for column in range(runtime.maze.width):
                runtime.maze.cells.append(
                    EmptyCell(position=GridPosition(column=column, row=row))
                )

        # Place the walls
        for wall in self.walls:
            runtime.maze.setCellAt(wall.position.column, wall.position.row, WallCell())


        # Create and configure the robot state
        runtime.maze.robot = Robot(
            position=GridPosition(
                column=self.robot_position.column,
                row=self.robot_position.row
            ),
            direction=Direction.NORTH
        )

# Program / Sequence of Commands
class Program(AbstractSyntaxElement, metaclass=MetaEClass):

    commands = EReference(eType=Command, lower=0, upper=-1, containment=True)

    def evaluate(self, runtime: RuntimeState) -> None:

        # Initialize the runtime state when starting the execution
        runtime.elements = [ Maze(name="maze") ]

        return loop(self.commands, lambda cmd: cmd.evaluate(runtime))
