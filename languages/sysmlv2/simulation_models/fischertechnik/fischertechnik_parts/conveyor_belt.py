import math
from dataclasses import dataclass

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import DirectionKind, ConveyorCommandKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.movement_computation_model import rotate_offset, cb_step_position, CB_STEP_SIZE_PER_TICK
from languages.sysmlv2.simulation_models.generic import PartSimulationModel

# Model-unit distance between a belt's feed and swap sensor positions --
# the span a token actually rides across, end to end.
# In reality, let's say right now the full length is 24cm
FEED_TO_SWAP_LENGTH = 4

# Model-unit distance across the belt's full ownable extent: FEED_TO_SWAP_LENGTH
# In reality, let's say right now the full length is 30cm
FULL_LENGTH = 6

# A token within this distance of a sensor's coordinate counts as
# "arrived" -- since cb_step_position() moves continuously now (no
# per-step rounding), a token's position isn't guaranteed to land
# exactly on the sensor's coordinate the way exact `==` would require,
# even though CB_STEP_SIZE_PER_TICK evenly divides FEED_TO_SWAP_LENGTH/
# FULL_LENGTH in exact arithmetic (float accumulation still drifts by a
# tiny amount). Half a step-size is generous enough to absorb that drift
# while still being far smaller than one step, so it can't cause a token
# to register as "arrived" a whole step early.
SENSOR_ARRIVAL_TOLERANCE = CB_STEP_SIZE_PER_TICK / 2


@dataclass(frozen=True)
class ConveyorBeltMachineSnapshot:
    """One `ConveyorBeltMachine`'s full dynamic state as of one
    `Factory.tick()` -- the per-machine value inside the Factory-wide
    snapshot TODAYS-TASKS.md's published-snapshot design (step 1) publishes
    once per tick. Mirrors every live property on `ConveyorBeltMachine`
    itself, since a guard's `AttributeReference` can ask for any of them,
    not just the ones today's demo panel happens to display.

    Frozen (and every field here is itself immutable -- `FactoryCoordinate`
    has no setters, the enums are plain enum members, everything else is a
    plain bool/int) so a reference to one of these can be safely read from
    another thread without risk of the machine it was copied from mutating
    the copy underneath a reader -- see facade_proxy.py's `SimulationBridge`
    docstring for the thread-confinement design this is part of.

    Declared before `ConveyorBeltMachine` in this file (rather than after,
    which would read more naturally) because `ConveyorBeltMachine` sets
    `snapshot_type = ConveyorBeltMachineSnapshot` as a class attribute,
    which needs this name to already exist. Built from a live
    `ConveyorBeltMachine` via `PartSimulationModel.snapshot()`
    (`generic.py`) -- reflects over this dataclass's own field list rather
    than needing a hand-written mapping here.
    """
    placementCoordinate: FactoryCoordinate
    conveyorSensFeed: bool
    conveyorSensSwap: bool
    conveyorSensImpulse: int
    currentCommand: ConveyorCommandKind | None
    direction: DirectionKind
    currentStepCount: int
    targetStepCount: int


class ConveyorBeltMachine(PartSimulationModel):

    snapshot_type = ConveyorBeltMachineSnapshot

    def __init__(self, factory: Factory):
        super().__init__()

        self._factory = factory

        self._currentCommand: ConveyorCommandKind = None
        self._direction: DirectionKind = DirectionKind.FORWARD
        self._currentStepCount : int = 0
        self._targetStepCount : int = 0

        self._conveyorSensImpulse : int = 0
        self._placementCoordinate : FactoryCoordinate = None

    @property
    def placementCoordinate(self):
        return self._placementCoordinate

    @placementCoordinate.setter
    def placementCoordinate(self, value):
        self._placementCoordinate = value

    @property
    def conveyorSensFeed(self):
        feed = self.feed_position()
        return any(math.isclose(token.position.x, feed.x, abs_tol=SENSOR_ARRIVAL_TOLERANCE)
                   and math.isclose(token.position.y, feed.y, abs_tol=SENSOR_ARRIVAL_TOLERANCE)
                   for token in self._factory.tokens_on(self))

    @property
    def conveyorSensSwap(self):
        swap = self.swap_position()
        return any(math.isclose(token.position.x, swap.x, abs_tol=SENSOR_ARRIVAL_TOLERANCE)
                   and math.isclose(token.position.y, swap.y, abs_tol=SENSOR_ARRIVAL_TOLERANCE)
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

    def _end_position(self, local_x_offset: float) -> FactoryCoordinate:
        """Coordinate of a feed/swap end: local_x_offset along the belt's
        own unrotated x-axis, rotated by placementCoordinate.degrees around
        its center. Rounded to the nearest grid cell -- these are fixed
        structural reference points (unlike a token's own continuously-
        moving position, cb_step_position()), so keeping them clean whole
        numbers is deliberate, not a FactoryCoordinate-wide constraint.
        Exact (no rounding needed in principle) for 0/90/180/270 degree
        rotations.
        """
        dx, dy = rotate_offset(local_x_offset, self._placementCoordinate.degrees)
        return FactoryCoordinate(
            round(self._placementCoordinate.x + dx),
            round(self._placementCoordinate.y + dy),
            self._placementCoordinate.degrees,
        )

    def feed_position(self) -> FactoryCoordinate:
        return self._end_position(-FEED_TO_SWAP_LENGTH / 2)

    def swap_position(self) -> FactoryCoordinate:
        return self._end_position(FEED_TO_SWAP_LENGTH / 2)

    def pre_feed_position(self) -> FactoryCoordinate:
        """One step before the feed end -- the FULL_LENGTH boundary on the
        feed side: still ownable if a token sits here, but one step short of
        actually triggering conveyorSensFeed.
        """
        return self._end_position(-FULL_LENGTH / 2)

    def post_swap_position(self) -> FactoryCoordinate:
        """One step past the swap end -- the FULL_LENGTH boundary on the
        swap side, mirroring pre_feed_position().
        """
        return self._end_position(FULL_LENGTH / 2)

    def _local_x_offset(self, position: FactoryCoordinate) -> float:
        """Inverse of `_end_position`: given an absolute coordinate,
        returns how far it sits from the belt's center along the belt's
        own unrotated x-axis. Not rounded (unlike `_end_position`) --
        used against a continuously-moving token's position (the
        overshoot check in `_move_owned_tokens_one_step()`), where
        snapping to a grid cell first would make the boundary check up to
        half a model unit late or early.
        """
        theta = math.radians(self._placementCoordinate.degrees)
        dx = position.x - self._placementCoordinate.x
        dy = position.y - self._placementCoordinate.y
        return dx * math.cos(theta) + dy * math.sin(theta)

    def moveToSensor(self, direction):
        """Starts the belt moving toward whichever end sensor `direction`
        points at (FORWARD -> swap end, BACKWARD -> feed end). Only sets
        the command/direction -- like flipping a switch, nothing else --
        deliberately not even an arrival check: if a token is already
        sitting on the target sensor, `advance()`'s pre-move arrival check
        (see its docstring) catches that on the very next tick and stops
        immediately, without this method needing to know or care. Keeping
        this to exactly two assignments matters beyond just tidiness --
        see HOMEWORK-SAYYID.md task 1 on why a multi-step method here would
        be unsafe to call from a thread other than the one that owns
        `Factory` (currently not queue-backed yet -- see TODAYS-TASKS.md).
        """
        self._currentCommand = ConveyorCommandKind.MOVE_TO_SENSOR
        self._direction = direction

    def moveOut(self, direction):
        """Starts the belt moving `direction`, with the explicit goal of
        pushing the token off the belt's physical extent -- unlike
        moveToSensor, whose success condition is stopping exactly at the
        boundary, this one's success condition *is* leaving it (past
        FULL_LENGTH / 2, same as MOVE_NB_STEPS's overshoot handling in
        advance()). Only sets the command/direction
        -- the actual per-tick movement, overshoot-disowning, and
        completion check happen in advance()/Factory.tick().
        """
        self._currentCommand = ConveyorCommandKind.MOVE_OUT
        self._direction = direction

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

    def tick(self):
        """One tick's worth of work for this belt's active command --
        dispatches to whichever `_advance_*` method matches
        `currentCommand`, each encapsulating its own pre-condition (if
        any), the actual movement, and its own post-condition (if any) --
        see each method's docstring for its specific contract. No branch
        matches (and nothing happens) if `currentCommand` is None, though
        Factory.tick() already only calls this when it isn't.

        Called by Factory.tick(), already paced to the right cadence by
        the time this runs.
        """
        if self._currentCommand == ConveyorCommandKind.MOVE_TO_SENSOR:
            self._advance_move_to_sens()
        elif self._currentCommand == ConveyorCommandKind.MOVE_NB_STEPS:
            self._advance_move_nb_steps()
        elif self._currentCommand == ConveyorCommandKind.MOVE_OUT:
            self._advance_move_out()

    def _move_owned_tokens_one_step(self):
        """Moves every token this belt currently owns one step along
        `_direction`, disowning any that end up strictly past the belt's
        physical ends (see FULL_LENGTH). Shared by every `_advance_*`
        method that can actually move a token -- MOVE_TO_SENSOR only calls
        this once its own pre-condition (below) has ruled out "already
        arrived."
        """
        for token in self._factory.tokens_on(self):
            new_position = cb_step_position(token.position, self._placementCoordinate.degrees, self._direction)
            token.move_to(new_position)
            if abs(self._local_x_offset(new_position)) > FULL_LENGTH / 2:
                self._factory.transfer_token(token, None)

    def _advance_move_to_sens(self):
        """Pre-condition: already arrived at the target sensor? Stop
        without moving -- this is what makes MOVE_TO_SENSOR unable to
        overshoot, since it's checked *before* any movement happens this
        tick, whether "already there" means the token was there when
        moveToSensor() was called or a previous tick's move just landed it
        there. No post-condition: arriving as a *result* of this tick's
        move is caught by this same pre-condition on the next tick, not
        within this call (see advance()'s docstring on this timing).
        """
        arrived = self.conveyorSensSwap if self._direction == DirectionKind.FORWARD else self.conveyorSensFeed
        if arrived:
            self.stop()
            return
        self._move_owned_tokens_one_step()

    def _advance_move_out(self):
        """No pre-condition -- always moves. Post-condition: stop once
        this belt no longer owns any token -- the overshoot-disown inside
        `_move_owned_tokens_one_step()` is what actually releases it, this
        just notices and stops the command afterward.
        """
        self._move_owned_tokens_one_step()
        if not self._factory.tokens_on(self):
            self.stop()

    def _advance_move_nb_steps(self):
        """No pre-condition -- always moves. Post-condition: stop once
        `currentStepCount` reaches `targetStepCount`.
        """
        self._move_owned_tokens_one_step()
        self.record_step()
        if self._currentStepCount >= self._targetStepCount:
            self.stop()

    def record_step(self):
        self._currentStepCount += 1

    def stop(self):
        self._currentCommand = None
        self._currentStepCount = 0
        self._targetStepCount = 0

    def statusRequest(self):
        pass
