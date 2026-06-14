from pyecore.ecore import *

from core.language import RuntimeStateElement

# Directions which the robot can be looking at
Direction = EEnum("Direction")
Direction.eLiterals.append(EEnumLiteral("NORTH"))
Direction.eLiterals.append(EEnumLiteral("EAST"))
Direction.eLiterals.append(EEnumLiteral("SOUTH"))
Direction.eLiterals.append(EEnumLiteral("WEST"))


class GridPosition(EObject, metaclass=MetaEClass):
    """A position in the NxM grid maze (column/row coordinates)."""

    column = EAttribute(eType=EInt)
    row = EAttribute(eType=EInt)


class MazeCell(EObject, metaclass=MetaEClass):
    """A cell in the maze grid (abstract base)."""

    abstract = True
    position = EReference(eType=GridPosition, lower=1, upper=1, containment=False)

    def isEmptyCell(self) -> bool:
        """Returns True if this cell represents an empty cell."""
        return False

    def isWallCell(self) -> bool:
        """Returns True if this cell represents a wall."""
        return False

    def isStartCell(self) -> bool:
        """Returns True if this cell represents a start position."""
        return False

    def isDestinationCell(self) -> bool:
        """Returns True if this cell represents a destination."""
        return False

class EmptyCell(MazeCell, metaclass=MetaEClass):
    """An empty cell in the maze."""

    def isEmptyCell(self) -> bool:
        return True

class WallCell(MazeCell, metaclass=MetaEClass):
    """A wall cell in the maze."""

    def isWallCell(self) -> bool:
        return True

class StartCell(MazeCell, metaclass=MetaEClass):
    """A start position cell in the maze."""

    def isStartCell(self) -> bool:
        return True

class DestinationCell(MazeCell, metaclass=MetaEClass):
    """A destination cell in the maze."""

    def isDestinationCell(self) -> bool:
        return True


class Robot(RuntimeStateElement, metaclass=MetaEClass):
    """The robot's runtime state, including position and orientation."""

    position = EReference(eType=GridPosition, lower=1, upper=1, containment=False)
    direction = EAttribute(eType=Direction)


class Maze(RuntimeStateElement, metaclass=MetaEClass):
    """A maze modeled as an NxM grid with a starting point and destination."""

    width = EAttribute(eType=EInt)
    height = EAttribute(eType=EInt)

    cells = EReference(eType=MazeCell, lower=0, upper=-1, containment=True)

    start = EReference(eType=GridPosition, lower=1, upper=1, containment=False)
    destination = EReference(eType=GridPosition, lower=1, upper=1, containment=False)

    robot = EReference(eType=Robot, lower=1, upper=1, containment=True)

    def getCellAt(self, column: int, row: int) -> MazeCell:
        """Return the MazeCell at the given (column, row) position using index calculation.

        Args:
            column: The column index (0-based).
            row: The row index (0-based).

        Returns:
            The MazeCell at the specified position.

        Raises:
            IndexError: If the coordinates are out of bounds or no cells exist.
        """
        if len(self.cells) == 0:
            raise IndexError("Maze has no cells defined")

        # Calculate the linear index from column and row using row-major ordering
        index = row * self.width + column

        if index < 0 or index >= len(self.cells):
            raise IndexError(
                f"Position ({column}, {row}) is out of maze bounds (width={self.width}, height={self.height})"
            )

        return self.cells[index]

    def setCellAt(self, column: int, row: int, cell: MazeCell) -> None:
        """Set the MazeCell at the given (column, row) position.

        Args:
            column: The column index (0-based).
            row: The row index (0-based).
            cell: The MazeCell to place at the specified position.

        Raises:
            IndexError: If the coordinates are out of bounds.
        """
        if len(self.cells) == 0:
            raise IndexError("Maze has no cells defined")

         # Calculate the linear index from column and row using row-major ordering
        index = row * self.width + column

        if index < 0 or index >= len(self.cells):
            raise IndexError(
                f"Position ({column}, {row}) is out of maze bounds (width={self.width}, height={self.height})"
             )

        self.cells[index] = cell
