import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from languages.sysmlv2.simulation_models.fischertechnik import factory
from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import DirectionKind, ConveyorCommandKind, TokenColorKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts.conveyor_belt import CB_WIDTH, CB_STEP_SIZE_PER_TICK
from languages.sysmlv2.simulation_models.fischertechnik.machine import FischertechnikMachine
from languages.sysmlv2.simulation_models.fischertechnik.movement_computation_model import rotate_offset, cb_step_position
from languages.sysmlv2.simulation_models.fischertechnik.token import Token

# The belt's own physical housing, the length is 27.5cm and width is 6cm
# In model size, the length would be 5.5 and width is 1.1
SL_LENGTH: float = 7.6
SL_WIDTH: float = 4
BELT_WIDTH: float = CB_WIDTH

PISTON_WIDTH: float = 1.8
SORTED_TOKEN_PLATFORM_WIDTH: float = 1.1

#There is a tolerance gap of 5 cm on either end, where it is the placement for the sensor
END_OF_SL_TOLERANCE: float = 1.0

# The line split into four equal zones along its own length: the entry
# sensor, then one color-detection point per TokenColorKind (BLUE/WHITE/
# RED, same order as the sensor_SL_* properties/SLMessages below). Shared
# with SortingLineVisualization (imported from there, not redefined) so
# the drawn platforms and the actual sensing points can never drift apart.
SL_ZONE_LENGTH: float = SL_LENGTH / 4
SL_ZONE_OFFSETS: list[float] = [-SL_LENGTH / 2 + SL_ZONE_LENGTH * (i + 0.5) for i in range(4)]

# Same per-tick pace as ConveyorBeltMachine's own CB_STEP_SIZE_PER_TICK
# (imported, not independently re-derived) -- both belts should visibly
# move at the same speed, and both this belt's own forward stepping and
# the piston's sideways push onto a platform (_step_toward_platform) use
# this one constant, so nothing in the sorting line moves faster than a
# token does on an actual conveyor belt. SL_LENGTH (152), SL_ZONE_LENGTH
# (38), and the platform's own local-y offset in _platform_position (51)
# all divide evenly by this, so nothing here needs its own step size.
SL_STEP_SIZE_PER_TICK: float = CB_STEP_SIZE_PER_TICK

# A token within this distance of a sensor's own position counts as
# "there" -- same halving reasoning as ConveyorBeltMachine's own
# SENSOR_ARRIVAL_TOLERANCE.
SENSOR_ARRIVAL_TOLERANCE: float = SL_STEP_SIZE_PER_TICK / 2

#Collection of event message that can be emitted by Conveyor Belt
# Look at the SysML models, package ConveyorBeltMessages
class SLMessages(Enum):
    BLUE_TOKEN_AVAILABLE = 'BlueTokenAvailableBufferedMessage'
    WHITE_TOKEN_AVAILABLE = 'WhiteTokenAvailableBufferedMessage'
    RED_TOKEN_AVAILABLE = 'RedTokenAvailableBufferedMessage'
    COMMAND_SUCCESS = 'CommandSuccessEventMessage'

@dataclass(frozen=True)
class SortingLineMachineSnapshot:

    sensor_SL_in: bool = False
    sensor_SL_blue: bool = False
    sensor_SL_white: bool = False
    sensor_SL_red: bool = False

    placementCoordinate: FactoryCoordinate = None


class SortingLineMachine(FischertechnikMachine):

    snapshot_type = SortingLineMachineSnapshot

    def __init__(self, factory: Factory):
        super().__init__(factory)

        self._placementCoordinate : FactoryCoordinate = None

    @property
    def placementCoordinate(self):
        return self._placementCoordinate

    @placementCoordinate.setter
    def placementCoordinate(self, value):
        self._placementCoordinate = value

    def _end_position(self, local_x_offset: float) -> FactoryCoordinate:
        """Coordinate `local_x_offset` model units along this line's own
        unrotated x-axis from its center, rotated by
        placementCoordinate.degrees -- same primitive
        ConveyorBeltMachine._end_position() uses for its own feed/swap
        endpoints.
        """
        dx, dy = rotate_offset(local_x_offset, self._placementCoordinate.degrees)
        return FactoryCoordinate(
            self._placementCoordinate.x + dx,
            self._placementCoordinate.y + dy,
            self._placementCoordinate.degrees,
        )

    def in_sensor_position(self) -> FactoryCoordinate:
        return self._end_position(SL_ZONE_OFFSETS[0])

    def blue_zone_position(self) -> FactoryCoordinate:
        return self._end_position(SL_ZONE_OFFSETS[1])

    def white_zone_position(self) -> FactoryCoordinate:
        return self._end_position(SL_ZONE_OFFSETS[2])

    def red_zone_position(self) -> FactoryCoordinate:
        return self._end_position(SL_ZONE_OFFSETS[3])

    def _zone_position(self, color: TokenColorKind) -> FactoryCoordinate:
        """Whichever of blue_zone_position()/white_zone_position()/
        red_zone_position() corresponds to `color` -- same
        TokenColorKind-to-zone mapping SortingLineVisualization's own
        zip(TokenColorKind, _STATION_OFFSETS) draws its platforms from.
        This is a point *on the belt itself*, where the piston for
        `color` is physically mounted (see SortingLineVisualization's own
        cylinder_rect) -- it's not what sensor_SL_blue/white/red read
        (those are occupancy sensors at the platform, _platform_position,
        not this on-belt trigger point). Used by _at_own_zone() to
        recognize a token that's just reached the point where its own
        piston can fire, the same way real hardware identifies a token by
        color once, wherever that happens, then just needs to know when
        it's physically at the right spot to act -- not by reading color
        again at each candidate zone.
        """
        return {
            TokenColorKind.BLUE: self.blue_zone_position,
            TokenColorKind.WHITE: self.white_zone_position,
            TokenColorKind.RED: self.red_zone_position,
        }[color]()

    def _token_at(self, position: FactoryCoordinate, color: Optional[TokenColorKind] = None) -> Optional[Token]:
        """The Token (if any) this line currently owns that sits within
        SENSOR_ARRIVAL_TOLERANCE of `position` -- same ownership-gated,
        tolerance-matched lookup as TokenProducerMachine's own
        _token_at_platform(), just against an arbitrary position rather
        than a single fixed platform_position(). If `color` is given,
        only a token of that exact color counts as a match -- a real
        color sensor at a color zone only fires for its own color, it
        doesn't just report "something's here" the way the entry sensor
        (sensor_SL_in, no color to check) does. _token_near (below) is
        this reduced to a bool for the sensor_SL_* properties; eject()
        uses this directly since it needs the Token itself, not just
        whether one is there.
        """
        return next((token for token in self._factory.tokens_on(self)
                     if (color is None or token.color == color)
                     and math.isclose(token.position.x, position.x, abs_tol=SENSOR_ARRIVAL_TOLERANCE)
                     and math.isclose(token.position.y, position.y, abs_tol=SENSOR_ARRIVAL_TOLERANCE)),
                    None)

    def _token_near(self, position: FactoryCoordinate, color: Optional[TokenColorKind] = None) -> bool:
        """Whether a token this line currently owns (of `color`, if given)
        sits within SENSOR_ARRIVAL_TOLERANCE of `position` -- shared by
        every sensor_SL_* property below, same computed-live "any(...)"
        pattern ConveyorBeltMachine's own conveyorSensFeed/conveyorSensSwap
        use (a real sensor read every time it's asked, not a cached flag).
        """
        return self._token_at(position, color) is not None

    def _at_own_zone(self, token: Token) -> bool:
        """Whether `token` currently sits at *its own* color's on-belt
        zone position -- e.g. a BLUE token at blue_zone_position(), not
        merely at some color zone. This is the piston's own trigger
        point, decided purely by the token's own color (already known,
        not "discovered" by testing each zone in turn) -- a RED token
        still crossing the blue/white zones must not register there,
        only once it physically reaches the red zone.
        """
        zone = self._zone_position(token.color)
        return math.isclose(token.position.x, zone.x, abs_tol=SENSOR_ARRIVAL_TOLERANCE) \
            and math.isclose(token.position.y, zone.y, abs_tol=SENSOR_ARRIVAL_TOLERANCE)

    def _at_own_platform(self, token: Token) -> bool:
        """Whether `token` is already parked on *its own* color's
        platform -- lets _advance_belt() recognize a token that's already
        been diverted, so it's left alone instead of being stepped
        forward (or re-diverted) again.
        """
        platform = self._platform_position(token.color)
        return math.isclose(token.position.x, platform.x, abs_tol=SENSOR_ARRIVAL_TOLERANCE) \
            and math.isclose(token.position.y, platform.y, abs_tol=SENSOR_ARRIVAL_TOLERANCE)

    def _off_belt_centerline(self, token: Token) -> bool:
        """Whether `token` currently sits away from the belt's own travel
        axis (local y != 0) -- the only way a token ever gets off that
        axis in the first place is a diversion already in progress (see
        _advance_belt()), so together with _at_own_platform (checked
        first, and false by the time this is reached) this is enough to
        recognize "still mid-diversion, not there yet" without any
        separate per-token state to track.
        """
        return not math.isclose(self._local_y_offset(token.position), 0.0, abs_tol=SENSOR_ARRIVAL_TOLERANCE)

    def _step_toward_platform(self, token: Token) -> None:
        """Moves `token` one tick's worth of travel further across the
        housing/platform gap, toward its own color's platform -- same
        per-tick pace as the belt's own forward stepping
        (SL_STEP_SIZE_PER_TICK), just along the perpendicular (local y)
        axis instead of local x (cb_step_position with degrees + 90 steps
        along local y the same way plain degrees steps along local x --
        see rotate_offset). Clamped so it never overshoots the platform,
        same "never overshoot, land exactly on arrival" shape
        encoder_changes_per_tick() uses for VacuumGripperMachine's own
        encoder axes.
        """
        target_y = self._local_y_offset(self._platform_position(token.color))
        remaining = target_y - self._local_y_offset(token.position)
        step = min(SL_STEP_SIZE_PER_TICK, remaining)
        token.move_to(cb_step_position(token.position, self._placementCoordinate.degrees + 90,
                                        DirectionKind.FORWARD, step))

    @property
    def sensor_SL_in(self):
        """Whether a token is currently at the entry. Color-blind by
        design -- unlike sensor_SL_blue/white/red below, this is purely a
        presence check, matching the plain Boolean it's declared as in
        the .sysml model.
        """
        return self._token_near(self.in_sensor_position())

    @property
    def sensor_SL_blue(self):
        """Whether a BLUE token currently occupies the blue platform --
        an occupancy sensor at _platform_position(BLUE), not an arrival
        sensor on the belt itself. Identifying a token's color doesn't
        happen here or at any of the three color zones: it's already
        known the moment the token exists (token.color), the same way
        sensor_SL_in already "knows" which platform a token is headed for
        as soon as it's at the entry -- these three sensors only report
        whether that already-decided token has actually arrived and is
        sitting on its platform yet.
        """
        return self._token_near(self._platform_position(TokenColorKind.BLUE), TokenColorKind.BLUE)

    @property
    def sensor_SL_white(self):
        """See sensor_SL_blue -- same occupancy check, WHITE platform."""
        return self._token_near(self._platform_position(TokenColorKind.WHITE), TokenColorKind.WHITE)

    @property
    def sensor_SL_red(self):
        """See sensor_SL_blue -- same occupancy check, RED platform."""
        return self._token_near(self._platform_position(TokenColorKind.RED), TokenColorKind.RED)

    def _local_x_offset(self, position: FactoryCoordinate) -> float:
        """How far `position` sits from this line's own center along its
        unrotated x-axis (the travel direction) -- same primitive
        ConveyorBeltMachine._local_x_offset() uses for its own overshoot
        check.
        """
        theta = math.radians(self._placementCoordinate.degrees)
        dx = position.x - self._placementCoordinate.x
        dy = position.y - self._placementCoordinate.y
        return dx * math.cos(theta) + dy * math.sin(theta)

    def _local_y_offset(self, position: FactoryCoordinate) -> float:
        """Companion to _local_x_offset: how far `position` sits from this
        line's own center along its unrotated y-axis (across travel).
        """
        theta = math.radians(self._placementCoordinate.degrees)
        dx = position.x - self._placementCoordinate.x
        dy = position.y - self._placementCoordinate.y
        return -dx * math.sin(theta) + dy * math.cos(theta)

    def _platform_position(self, color: TokenColorKind) -> FactoryCoordinate:
        """Where a token gets diverted to once it reaches its own color's
        zone (_zone_position) on the belt: the same along-travel (local
        x) position as that zone, pushed across travel (local y) far
        enough to clear the belt (past SL_WIDTH / 2, the housing's own
        edge) and land at the midpoint of that station's drawn platform
        (SORTED_TOKEN_PLATFORM_WIDTH / 2 further out) -- same platform_rect
        placement SortingLineVisualization draws, so a diverted token
        visually lands on its own platform rather than mid-air past the
        housing edge. This is also what sensor_SL_blue/white/red actually
        read (occupancy), and what eject() looks for a token already
        parked at to release. Built the same way _end_position() rotates
        a local x-only offset, just with a local y component added in too
        (local +y being "out toward the platform" -- see _local_y_offset).
        """
        local_x_offset = self._local_x_offset(self._zone_position(color))
        local_y_offset = SL_WIDTH / 2 + SORTED_TOKEN_PLATFORM_WIDTH / 2
        theta = math.radians(self._placementCoordinate.degrees)
        dx = local_x_offset * math.cos(theta) - local_y_offset * math.sin(theta)
        dy = local_x_offset * math.sin(theta) + local_y_offset * math.cos(theta)
        return FactoryCoordinate(
            self._placementCoordinate.x + dx,
            self._placementCoordinate.y + dy,
            self._placementCoordinate.degrees,
        )

    def contains_position(self, position: FactoryCoordinate) -> bool:
        """Whether `position` falls on the belt track itself (not the
        wider housing/platforms to either side) -- along travel, within
        SL_LENGTH / 2 of center; across travel, within BELT_WIDTH / 2.
        Same shape as ConveyorBeltMachine.contains_position().
        """
        within_length = abs(self._local_x_offset(position)) <= SL_LENGTH / 2
        within_width = abs(self._local_y_offset(position)) <= BELT_WIDTH / 2
        return within_length and within_width

    def eject(self, color: TokenColorKind):
        """
        This method will instruct the sorting line to eject a token from a platform (if exist)
        that correspond to the desired colo
        :param color:
        :return:

        Emits the same CommandSuccessEventMessage tick() emits for "a
        token was successfully sorted" -- see tick()'s own docstring for
        why these two currently share one message name/type.
        """
        token = self._token_at(self._platform_position(color), color)
        if token is not None:
            self._factory.transfer_token(token, self._factory.machine_at(token.position))
        self.emit_event_to_factory(SLMessages.COMMAND_SUCCESS)

    def stop(self):

        pass

    def is_idle(self) -> bool:
        """Always False: this line's belt never stops on its own (see
        tick()) -- there's no command/idle sentinel to check, unlike
        ConveyorBeltMachine, so Factory.tick() must dispatch this machine
        every paced step, forever.
        """
        return False

    def tick(self) -> None:
        """This line never idles (see is_idle()): every tick, its belt
        advances whatever tokens it currently owns one step further along
        -- one-way, no direction/command concept to start or stop (unlike
        ConveyorBeltMachine's MOVE_TO_SENSOR/MOVE_OUT) -- and its three
        platform-occupancy sensors (sensor_SL_blue/white/red) are freshly
        re-checked for a rising edge, each reporting its own
        *_TOKEN_AVAILABLE message the moment a token actually becomes
        available on that platform (not merely the moment it passes that
        zone on the belt -- see sensor_SL_blue's own docstring), alongside
        a COMMAND_SUCCESS -- "a token was successfully sorted" is exactly
        this edge, so this is the only other place besides eject() that
        emits it. The two mean different things (this: a token just
        arrived on a platform; eject(): a release command just finished,
        whether or not anything was there) but share the one message
        name/type -- nothing currently listens for it scoped by source
        (`via sortingLine`) or distinguishes the two, so any future
        mission wiring built on CommandSuccessEventMessage needs to
        account for both call sites firing it. sensor_SL_in has no
        matching SLMessages entry, so it isn't edge-checked here --
        SortingLineSimpleMission polls it directly as a guard condition
        instead (see the .sysml model).

        A token reaching its own zone on the belt (_at_own_zone, decided
        by its own already-known color, not by re-checking it at each
        candidate zone) gets diverted sideways onto that color's own
        platform starting one tick later (see _advance_belt()), stepping
        across the gap at the same per-tick pace as its own forward
        travel, until it arrives and sensor_SL_blue/white/red (whichever
        matches) turns True. A token that reaches the far end without
        ever matching its own zone simply falls off the line instead
        (disowned, same overshoot handling
        ConveyorBeltMachine._move_owned_tokens_one_step() uses).
        """
        self._advance_belt()

        if self._sensor_edge('sensor_SL_blue', self.sensor_SL_blue) is True:
            self.emit_event_to_factory(SLMessages.BLUE_TOKEN_AVAILABLE)
            self.emit_event_to_factory(SLMessages.COMMAND_SUCCESS)
        if self._sensor_edge('sensor_SL_white', self.sensor_SL_white) is True:
            self.emit_event_to_factory(SLMessages.WHITE_TOKEN_AVAILABLE)
            self.emit_event_to_factory(SLMessages.COMMAND_SUCCESS)
        if self._sensor_edge('sensor_SL_red', self.sensor_SL_red) is True:
            self.emit_event_to_factory(SLMessages.RED_TOKEN_AVAILABLE)
            self.emit_event_to_factory(SLMessages.COMMAND_SUCCESS)

    def _advance_belt(self) -> None:
        """Moves every token this line currently owns one step further
        along -- except a token already parked on its own platform
        (_at_own_platform), which stays put until eject() releases it.
        A token that was already sitting at *its own* on-belt zone at the
        *start* of this tick (_at_own_zone -- the piston's own trigger
        point, decided by the token's already-known color, not a
        "sensor" in the sensor_SL_* sense), or is already partway across
        the housing/platform gap from a previous tick's diversion
        (_off_belt_centerline -- _at_own_platform, checked first, already
        ruled out "arrived"), gets stepped sideways one tick further
        toward that platform (_step_toward_platform) instead of taking a
        forward step. A token of the "wrong" color for the zone it's
        currently passing through (e.g. a RED token still at the blue
        zone) matches neither check, so it just keeps stepping forward
        like any other token -- only its own zone, further along, ever
        diverts it. Any token that reaches the far end without ever
        matching its own zone falls off the line instead (disowned, same
        overshoot handling ConveyorBeltMachine._move_owned_tokens_one_step()
        uses), shared movement primitive (cb_step_position/rotate_offset)
        ConveyorBeltMachine also builds its own stepping on, always
        FORWARD since this line has no reverse concept.

        The sideways diversion is checked against position *before* this
        tick's own movement, so it never fires on the same tick a token's
        forward step first lands it at its own zone -- arrival and the
        first step of diversion stay two separate, one-tick-apart events,
        same "checked before this tick's own move" shape
        ConveyorBeltMachine's own MOVE_TO_SENSOR pre-condition uses for
        the same reason. sensor_SL_blue/white/red aren't affected by this
        either way -- they only read True once the token actually reaches
        the platform, well after this arrival tick.
        """
        for token in self._factory.tokens_on(self):
            if self._at_own_platform(token):
                continue

            if self._at_own_zone(token) or self._off_belt_centerline(token):
                self._step_toward_platform(token)
                continue

            new_position = cb_step_position(token.position, self._placementCoordinate.degrees,
                                             DirectionKind.FORWARD, SL_STEP_SIZE_PER_TICK)
            token.move_to(new_position)
            if not self.contains_position(new_position):
                self._factory.transfer_token(token, None)