import math
from dataclasses import dataclass
from enum import Enum

from languages.sysmlv2.simulation_models.fischertechnik import factory
from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import DirectionKind, ConveyorCommandKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.movement_computation_model import rotate_offset, cb_step_position
from languages.sysmlv2.simulation_models.generic import PartSimulationModel

# The belt's own physical housing, the length is 27.5cm and width is 6cm
# In model size, the length would be 5.5 and width is 1.1
CB_LENGTH: float = 5.5
CB_WIDTH: float = 1.1

#There is a tolerance gap of 5 cm on either end, where it is the placement for the sensor
END_OF_CB_TOLERANCE: float = 1.0

# Model-unit distance between a belt's feed and swap sensor positions --
# the span a token actually rides across, end to end. Derived from the
# belt's own physical length (CB_LENGTH) minus the sensor's inset from
# each end (END_OF_CB_TOLERANCE) -- was an independently guessed
# placeholder (4) before those real measurements existed.
FEED_TO_SWAP_LENGTH = CB_LENGTH - 2 * END_OF_CB_TOLERANCE

# Largest step that evenly divides both CB_LENGTH and FEED_TO_SWAP_LENGTH
# (math.gcd, scaled to/from integers -- `* 100`/`/ 100` assumes at most 2
# decimal places of model-unit precision, i.e. 0.01 model units = 0.05cm
# real, finer than a hand measurement warrants), then split into 10 ticks
# -- the actual speed knob. Guarantees a token moving between any of the
# belt's own structural points (pre_feed/feed/swap/post_swap) always
# lands exactly on the next one, however CB_LENGTH/END_OF_CB_TOLERANCE
# end up being remeasured, with no need to hand-verify divisibility.
CB_STEP_SIZE_PER_TICK: float = math.gcd(round(CB_LENGTH * 100), round(FEED_TO_SWAP_LENGTH * 100)) / 100 / 10

# A token within this distance of a sensor's coordinate counts as
# "arrived" -- since cb_step_position() moves continuously now (no
# per-step rounding), a token's position isn't guaranteed to land
# exactly on the sensor's coordinate the way exact `==` would require,
# even though CB_STEP_SIZE_PER_TICK evenly divides FEED_TO_SWAP_LENGTH/
# CB_LENGTH in exact arithmetic (float accumulation still drifts by a
# tiny amount). Half a step-size is generous enough to absorb that drift
# while still being far smaller than one step, so it can't cause a token
# to register as "arrived" a whole step early.
SENSOR_ARRIVAL_TOLERANCE = CB_STEP_SIZE_PER_TICK / 2

#Collection of event message that can be emitted by Conveyor Belt
# Look at the SysML models, package ConveyorBeltMessages
class CBEventMessages(Enum):

    FEED_FREE_EVENT = 'FeedFreeEventMessage'
    SWAP_BUSY_EVENT = 'SwapBusyEventMessage'
    COMMAND_SUCCESS = 'CBCommandSuccessEventMessage'
    STOP_EVENT = 'StopEventMessage'
    START_EVENT = 'StartEventMessage'

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
    currentCommand: ConveyorCommandKind
    direction: DirectionKind
    currentStepCount: int
    targetStepCount: int


class ConveyorBeltMachine(PartSimulationModel):

    snapshot_type = ConveyorBeltMachineSnapshot

    def __init__(self, factory: Factory):
        super().__init__()

        self._factory = factory

        self._currentCommand: ConveyorCommandKind = ConveyorCommandKind.STOP
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

    def is_idle(self) -> bool:
        """STOP is this machine's own idle sentinel (not None -- see
        __init__/stop()), so it needs its own override of the base
        PartSimulationModel.is_idle() default.
        """
        return self._currentCommand == ConveyorCommandKind.STOP

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
        """One step before the feed end -- the CB_LENGTH boundary on the
        feed side: still ownable if a token sits here, but one step short of
        actually triggering conveyorSensFeed.
        """
        return self._end_position(-CB_LENGTH / 2)

    def post_swap_position(self) -> FactoryCoordinate:
        """One step past the swap end -- the CB_LENGTH boundary on the
        swap side, mirroring pre_feed_position().
        """
        return self._end_position(CB_LENGTH / 2)

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

    def _local_y_offset(self, position: FactoryCoordinate) -> float:
        """Companion to `_local_x_offset`: how far `position` sits from
        the belt's center along its own unrotated y-axis (perpendicular
        to travel) -- same rotation, the other component. Used by
        `contains_position()` for the belt's CB_WIDTH bound.
        """
        theta = math.radians(self._placementCoordinate.degrees)
        dx = position.x - self._placementCoordinate.x
        dy = position.y - self._placementCoordinate.y
        return -dx * math.sin(theta) + dy * math.cos(theta)

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
        CB_LENGTH / 2, same as MOVE_NB_STEPS's overshoot handling in
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
        matches STOP (this belt's idle sentinel -- see is_idle()), though
        Factory.tick() already only calls this when the machine isn't idle.

        Called by Factory.tick(), already paced to the right cadence by
        the time this runs.

        Sensor edge events (FeedFreeEvent/SwapBusyEvent) are checked
        before/after the dispatch, right here rather than inside any one
        _advance_* method -- these are plain local variables, not
        persisted instance state, so this only catches a transition
        caused by this tick's own dispatch (not e.g. a token placed on a
        sensor from outside this belt's own command, like the manual
        token-placement panel or another machine's grip()/release()).
        """
        swap_was_busy = self.conveyorSensSwap
        feed_was_occupied = self.conveyorSensFeed

        if self._currentCommand == ConveyorCommandKind.MOVE_TO_SENSOR:
            self._advance_move_to_sens()
        elif self._currentCommand == ConveyorCommandKind.MOVE_NB_STEPS:
            self._advance_move_nb_steps()
        elif self._currentCommand == ConveyorCommandKind.MOVE_OUT:
            self._advance_move_out()

        if self.conveyorSensSwap and not swap_was_busy:
            self.emit_event_to_factory(CBEventMessages.SWAP_BUSY_EVENT)
        if feed_was_occupied and not self.conveyorSensFeed:
            self.emit_event_to_factory(CBEventMessages.FEED_FREE_EVENT)

    def contains_position(self, position: FactoryCoordinate) -> bool:
        """Whether `position` falls within this belt's own physical
        footprint: along travel, as far out as post_swap_position()
        itself sits (not a separately re-derived CB_LENGTH / 2 -- reusing
        the same rounded reference point _end_position() already produces
        means pre_feed_position()/post_swap_position() can never fall
        just outside their own boundary, whatever CB_LENGTH happens to
        be); across travel, within CB_WIDTH / 2 of center. Same length
        check `_move_owned_tokens_one_step()` already used inline for its
        disown condition, now the single source of truth for both that
        and any future ownership-by-geometry query (e.g. a released token
        landing on this belt).
        """
        within_length = abs(self._local_x_offset(position)) <= self._local_x_offset(self.post_swap_position())
        within_width = abs(self._local_y_offset(position)) <= CB_WIDTH / 2
        return within_length and within_width

    def record_step(self):
        self._currentStepCount += 1

    def stop(self):
        self._currentCommand = ConveyorCommandKind.STOP
        self._currentStepCount = 0
        self._targetStepCount = 0
        self.emit_event_to_factory(CBEventMessages.COMMAND_SUCCESS)

    def statusRequest(self):
        pass

    def _move_owned_tokens_one_step(self):
        """Moves every token this belt currently owns one step along
        `_direction`, disowning any that end up strictly past the belt's
        physical ends (see CB_LENGTH). Shared by every `_advance_*`
        method that can actually move a token -- MOVE_TO_SENSOR only calls
        this once its own pre-condition (below) has ruled out "already
        arrived."
        """
        for token in self._factory.tokens_on(self):
            new_position = cb_step_position(token.position, self._placementCoordinate.degrees, self._direction,
                                            CB_STEP_SIZE_PER_TICK)
            token.move_to(new_position)
            if not self.contains_position(new_position):
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

    def emit_event_to_factory(self, event: CBEventMessages):
        self._factory.record_event(event.value, self.name)