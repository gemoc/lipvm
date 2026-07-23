import math

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import DirectionKind, ConveyorCommandKind
from languages.sysmlv2.simulation_models.generic import PartSimulationModel

# Model-unit distance from a belt's placementCoordinate to each of its
# feed/swap ends (matches the visualization's BELT_WIDTH/SCALE ratio).
HALF_LENGTH = 2


class ConveyorBeltMachine(PartSimulationModel):

    def __init__(self, factory):

        self._factory = factory

        self._currentCommand: ConveyorCommandKind = None
        self._direction: DirectionKind = DirectionKind.FORWARD
        self._currentStepCount : int = 0
        self._targetStepCount : int = 0

        self._conveyorSensFeed : bool = False
        self._conveyorSensSwap : bool = False
        self._conveyorSensImpulse : int = 0
        self._placementCoordinate : FactoryCoordinate

    @property
    def placementCoordinate(self):
        return self._placementCoordinate

    @placementCoordinate.setter
    def placementCoordinate(self, value):
        self._placementCoordinate = value

    @property
    def conveyorSensFeed(self):
        return self._conveyorSensFeed

    @property
    def conveyorSensSwap(self):
        return self._conveyorSensSwap

    @property
    def conveyorSensImpulse(self):
        return self._conveyorSensImpulse

    @property
    def currentCommand(self):
        return self._currentCommand

    @property
    def direction(self):
        return self._direction

    def _end_position(self, local_x_offset: int) -> FactoryCoordinate:
        """Coordinate of a feed/swap end: local_x_offset along the belt's
        own unrotated x-axis, rotated by placementCoordinate.degrees around
        its center. Rounded to the nearest grid cell since FactoryCoordinate
        is integer-only -- exact for 0/90/180/270 degree rotations.
        """
        theta = math.radians(self._placementCoordinate.degrees)
        dx = local_x_offset * math.cos(theta)
        dy = local_x_offset * math.sin(theta)
        return FactoryCoordinate(
            round(self._placementCoordinate.x + dx),
            round(self._placementCoordinate.y + dy),
            self._placementCoordinate.degrees,
        )

    def feed_position(self) -> FactoryCoordinate:
        return self._end_position(-HALF_LENGTH)

    def swap_position(self) -> FactoryCoordinate:
        return self._end_position(HALF_LENGTH)

    def _local_x_offset(self, position: FactoryCoordinate) -> int:
        """Inverse of `_end_position`: given an absolute coordinate that
        lies on this belt's axis, returns how far it sits from the belt's
        center along the belt's own unrotated x-axis. Exact (no drift) for
        0/90/180/270 degree placements, same as `_end_position`.
        """
        theta = math.radians(self._placementCoordinate.degrees)
        dx = position.x - self._placementCoordinate.x
        dy = position.y - self._placementCoordinate.y
        return round(dx * math.cos(theta) + dy * math.sin(theta))

    def update_sensors(self):
        """Refreshes conveyorSensFeed/conveyorSensSwap from the tokens
        currently owned by this belt. A Token is just a point in this model,
        so "the whole token occupies the position" is an exact coordinate
        match against the feed/swap end.
        """
        positions = [token.position for token in self._factory.tokens_on(self)]
        feed, swap = self.feed_position(), self.swap_position()
        self._conveyorSensFeed = any(p.x == feed.x and p.y == feed.y for p in positions)
        self._conveyorSensSwap = any(p.x == swap.x and p.y == swap.y for p in positions)

    def moveToSensor(self, direction):
        """Moves every token currently on this belt directly to whichever
        end sensor `direction` points at (FORWARD -> swap end, BACKWARD ->
        feed end) -- a discrete jump, matching the simulation's current
        motion model (see TODO-LIST.md).
        """
        target = self.swap_position() if direction == DirectionKind.FORWARD else self.feed_position()
        for token in self._factory.tokens_on(self):
            token.move_to(target)
        self.update_sensors()

    def moveOut(self, direction):
        pass

    def moveNbSteps(self, steps, direction):
        """Moves every token currently on this belt `steps` model-grid
        units along the belt's own axis -- toward the swap end for FORWARD,
        toward the feed end for BACKWARD -- clamped so it can't overshoot
        past either end.
        """
        sign = 1 if direction == DirectionKind.FORWARD else -1
        for token in self._factory.tokens_on(self):
            offset = self._local_x_offset(token.position) + sign * steps
            offset = max(-HALF_LENGTH, min(HALF_LENGTH, offset))
            token.move_to(self._end_position(offset))
        self.update_sensors()

    def stop(self):
        pass

    def statusRequest(self):
        pass
