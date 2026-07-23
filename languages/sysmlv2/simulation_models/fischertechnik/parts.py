import math

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import DirectionKind, ConveyorCommandKind
from languages.sysmlv2.simulation_models.fischertechnik.movement_computation_model import rotate_offset, cb_step_position
from languages.sysmlv2.simulation_models.generic import PartSimulationModel

# Model-unit distance from a belt's placementCoordinate to each of its
# feed/swap ends (matches the visualization's BELT_WIDTH/SCALE ratio).
HALF_LENGTH = 2

# Extra model units beyond HALF_LENGTH a token can travel before being
# disowned -- gives MOVE_NB_STEPS/MOVE_OUT one step of overshoot past the
# sensor positions before ownership is actually released, rather than
# disowning the instant a token passes feed_position()/swap_position().
OVERSHOOT_TOLERANCE = 1


class ConveyorBeltMachine(PartSimulationModel):

    def __init__(self, factory):

        self._factory = factory

        self._currentCommand: ConveyorCommandKind = None
        self._direction: DirectionKind = DirectionKind.FORWARD
        self._currentStepCount : int = 0
        self._targetStepCount : int = 0

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
        feed = self.feed_position()
        return any(token.position.x == feed.x and token.position.y == feed.y
                   for token in self._factory.tokens_on(self))

    @property
    def conveyorSensSwap(self):
        swap = self.swap_position()
        return any(token.position.x == swap.x and token.position.y == swap.y
                   for token in self._factory.tokens_on(self))

    @property
    def conveyorSensImpulse(self):
        return self._conveyorSensImpulse

    @property
    def currentCommand(self):
        return self._currentCommand

    @property
    def direction(self):
        return self._direction

    @property
    def currentStepCount(self):
        return self._currentStepCount

    @property
    def targetStepCount(self):
        return self._targetStepCount

    def _end_position(self, local_x_offset: int) -> FactoryCoordinate:
        """Coordinate of a feed/swap end: local_x_offset along the belt's
        own unrotated x-axis, rotated by placementCoordinate.degrees around
        its center. Rounded to the nearest grid cell since FactoryCoordinate
        is integer-only -- exact for 0/90/180/270 degree rotations.
        """
        dx, dy = rotate_offset(local_x_offset, self._placementCoordinate.degrees)
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
        """Inverse of `_end_position`: given an absolute coordinate,
        returns how far it sits from the belt's center along the belt's
        own unrotated x-axis. Exact (no drift) for 0/90/180/270 degree
        placements, same as `_end_position`.
        """
        theta = math.radians(self._placementCoordinate.degrees)
        dx = position.x - self._placementCoordinate.x
        dy = position.y - self._placementCoordinate.y
        return round(dx * math.cos(theta) + dy * math.sin(theta))

    def moveToSensor(self, direction):
        """Starts the belt moving toward whichever end sensor `direction`
        points at (FORWARD -> swap end, BACKWARD -> feed end) -- unless a
        token is already there, in which case there's nothing to move and
        starting the command anyway would push it one step past the end on
        the first tick (see advance()'s overshoot handling) instead of
        ever detecting arrival. Only sets the command/direction -- like
        flipping a switch -- the actual per-tick movement and boundary
        check happen in ConveyorBeltMachine.advance()/Factory.tick().
        """
        already_arrived = self.conveyorSensSwap if direction == DirectionKind.FORWARD else self.conveyorSensFeed
        if already_arrived:
            self.stop()
            return

        self._currentCommand = ConveyorCommandKind.MOVE_TO_SENSOR
        self._direction = direction
        self._currentStepCount = 0
        self._targetStepCount = 0

    def moveOut(self, direction):
        """Starts the belt moving `direction`, with the explicit goal of
        pushing the token off the belt's physical extent -- unlike
        moveToSensor, whose success condition is stopping exactly at the
        boundary, this one's success condition *is* leaving it (past
        HALF_LENGTH + OVERSHOOT_TOLERANCE, same as MOVE_NB_STEPS's
        overshoot handling in advance()). Only sets the command/direction
        -- the actual per-tick movement, overshoot-disowning, and
        completion check happen in advance()/Factory.tick().
        """
        self._currentCommand = ConveyorCommandKind.MOVE_OUT
        self._direction = direction
        self._currentStepCount = 0
        self._targetStepCount = 0

    def moveNbSteps(self, steps, direction):
        """Starts the belt moving `steps` model-grid units along its own
        axis -- toward the swap end for FORWARD, toward the feed end for
        BACKWARD. Only sets the command/direction/step boundary -- the
        actual per-tick movement and boundary check happen in
        Factory.advance()/tick().
        """
        self._currentCommand = ConveyorCommandKind.MOVE_NB_STEPS
        self._direction = direction
        self._currentStepCount = 0
        self._targetStepCount = steps

    def advance(self):
        """One tick's worth of work for this belt's active command: move
        its token(s) one step -- disowning any token that ends up strictly
        past the belt's physical ends (MOVE_NB_STEPS can overshoot;
        MOVE_TO_SENSOR can't, since arriving exactly at feed/swap is its
        own stop condition) -- then check whether the boundary for
        currentCommand was just reached, stopping itself if so. Called by
        Factory.tick(), already paced to the right cadence by the time
        this runs.
        """
        for token in self._factory.tokens_on(self):
            new_position = cb_step_position(token.position, self._placementCoordinate.degrees, self._direction)
            token.move_to(new_position)
            if abs(self._local_x_offset(new_position)) > HALF_LENGTH + OVERSHOOT_TOLERANCE:
                self._factory.transfer_token(token, None)

        if self._currentCommand == ConveyorCommandKind.MOVE_TO_SENSOR:
            arrived = self.conveyorSensSwap if self._direction == DirectionKind.FORWARD else self.conveyorSensFeed
            if arrived:
                self.stop()
        elif self._currentCommand == ConveyorCommandKind.MOVE_NB_STEPS:
            self.record_step()
            if self._currentStepCount >= self._targetStepCount:
                self.stop()
        elif self._currentCommand == ConveyorCommandKind.MOVE_OUT:
            if not self._factory.tokens_on(self):
                self.stop()

    def record_step(self):
        self._currentStepCount += 1

    def stop(self):
        self._currentCommand = None
        self._currentStepCount = 0
        self._targetStepCount = 0

    def statusRequest(self):
        pass
