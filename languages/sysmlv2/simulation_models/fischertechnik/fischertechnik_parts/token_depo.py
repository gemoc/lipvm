import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import TokenDepoCommandKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.movement_computation_model import rotate_offset
from languages.sysmlv2.simulation_models.fischertechnik.token import Token
from languages.sysmlv2.simulation_models.generic import PartSimulationModel

# This is a dummy machine. Thus, we can make our own model size
TOKEN_DEPO_BASE_LENGTH = 3
TOKEN_DEPO_BASE_WIDTH = 3
TOKEN_RECEIVER_LENGTH = 1.5
TOKEN_RECEIVER_WIDTH = 1.5

# Model-unit distance from the machine's own center to the receiver
# platform's center, along its local +x axis -- same
# TOKEN_PLATFORM_OFFSET reasoning as token_producer.py, mirrored here so
# receiver_position() and TokenDepoVisualization.draw() never drift apart.
TOKEN_RECEIVER_OFFSET = TOKEN_DEPO_BASE_LENGTH / 2 + TOKEN_RECEIVER_LENGTH / 2

# A token within this distance of receiver_position() counts as "on" the
# receiver platform -- same reasoning as ConveyorBeltMachine's own
# SENSOR_ARRIVAL_TOLERANCE (conveyor_belt.py): tokens land here exactly
# (the panel's Place button, or a future machine's release()), so this
# only needs to absorb float drift, not real positional slop -- kept
# smaller than the platform's own footprint so it can't falsely claim a
# token that merely landed nearby.
RECEIVER_ARRIVAL_TOLERANCE = min(TOKEN_RECEIVER_LENGTH, TOKEN_RECEIVER_WIDTH) / 2

class TokenDepoMessages(Enum):
    RECEIVER_EMPTY = 'ReceiverEmptyEventMessage'
    RECEIVER_BUSY = 'ReceiverBusyEventMessage'
    COMMAND_SUCCESS = 'TokenDepoSuccessEventMessage'

@dataclass(frozen=True)
class TokenDepoMachineSnapshot:
    currentCommand: Optional[TokenDepoCommandKind]
    tokenCount: int
    receiverSens: bool
    placementCoordinate: FactoryCoordinate

class TokenDepoMachine(PartSimulationModel):

    snapshot_type = TokenDepoMachineSnapshot

    def __init__(self, factory: Factory):
        super().__init__()

        self._factory = factory
        self._currentCommand: TokenDepoCommandKind = TokenDepoCommandKind.STOP
        self._tokenCount: int = 0
        self._placementCoordinate: FactoryCoordinate = None

        # The receiverSens value as of the end of the last tick() --
        # see is_idle()/tick()'s own docstrings for why this has to be
        # persisted across calls rather than captured fresh each time.
        self._was_receiver_busy: bool = False

    @property
    def placementCoordinate(self):
        return self._placementCoordinate

    @placementCoordinate.setter
    def placementCoordinate(self, value):
        self._placementCoordinate = value

    @property
    def currentCommand(self):
        return self._currentCommand

    @property
    def tokenCount(self):
        return self._tokenCount

    @property
    def receiverSens(self):
        return self._token_at_receiver() is not None

    def _token_at_receiver(self) -> Optional[Token]:
        """The Token currently owned by this machine that sits at
        receiver_position() (within RECEIVER_ARRIVAL_TOLERANCE), or None
        if the receiver is empty. `tokens_on(self)` rather than
        `factory.tokens` -- a token merely passing nearby without this
        machine owning it doesn't count, same ownership-gated shape as
        ConveyorBeltMachine.conveyorSensFeed/conveyorSensSwap.
        """
        receiver = self.receiver_position()
        for token in self._factory.tokens_on(self):
            if math.isclose(token.position.x, receiver.x, abs_tol=RECEIVER_ARRIVAL_TOLERANCE) and \
                    math.isclose(token.position.y, receiver.y, abs_tol=RECEIVER_ARRIVAL_TOLERANCE):
                return token
        return None

    def receiver_position(self) -> FactoryCoordinate:
        """Coordinate of the platform where a token is placed to be
        stored -- TOKEN_RECEIVER_OFFSET model units along the machine's
        own local +x axis, rotated by placementCoordinate.degrees. Same
        fixed-reference-point shape as ConveyorBeltMachine._end_position()'s
        feed_position()/swap_position().
        """
        dx, dy = rotate_offset(TOKEN_RECEIVER_OFFSET, self._placementCoordinate.degrees)
        return FactoryCoordinate(
            self._placementCoordinate.x + dx,
            self._placementCoordinate.y + dy,
            self._placementCoordinate.degrees,
        )

    def is_idle(self) -> bool:
        """Always False -- deliberately not the CB/VGR-style "STOP means
        nothing to advance" sentinel. This machine's receiver has to be
        watched every tick even when no storeToken/emptyReceiver command
        is running, since a token can land on it from outside (the
        panel's Place button, or another machine's action) at any time,
        and 'accept ReceiverBusyEventMessage via tokenDepoInstance' means
        only this machine's own tick() noticing that can ever report it
        -- nothing else is allowed to emit an event "via tokenDepoInstance"
        on this machine's behalf. Factory.tick() (factory.py) uses
        is_idle() to decide whether to call tick() at all, so returning
        False here is what keeps this machine ticking (at the same paced
        cadence as every other machine) even while at rest.
        """
        return False

    def storeToken(self):
        """
        This method allows the token that is currently placed in the receiver platform
        to be stored inside the machine. If there is no token in the receiver, then this
        method will do nothing.

        Only sets currentCommand -- like ConveyorBeltMachine.moveToSensor()/
        VacuumGripperMachine.pick(), the actual work (and its own "was
        there even a token to store" check) happens in tick()'s
        _advance_store_token(), not here.
        :return:
        """
        self._currentCommand = TokenDepoCommandKind.STORE_TOKEN

    def emptyReceiver(self):
        """
        This method ejects the token that is currently placed in the receiver platform. If
        there is no token in the receiver, then this method will do nothing.

        Only sets currentCommand -- see storeToken()'s docstring; the
        actual ejection happens in tick()'s _advance_empty_receiver().
        :return:
        """
        self._currentCommand = TokenDepoCommandKind.EMPTY_RECEIVER

    def stop(self):
        """
        Stop the token depo machine
        :return:
        """
        self._currentCommand = TokenDepoCommandKind.STOP
        self.emit_event_to_factory(TokenDepoMessages.COMMAND_SUCCESS)

    def emit_event_to_factory(self, event: TokenDepoMessages):
        self._factory.record_event(event.value, self.name)

    def tick(self) -> None:
        """Dispatches to whichever _advance_* method matches
        currentCommand (a no-op when it's STOP -- there's nothing to
        advance), then checks receiverSens for an edge transition against
        _was_receiver_busy (not a locally-captured "before" value --
        see is_idle()'s docstring: unlike ConveyorBeltMachine, whose own
        movement causes its sensor transition *inside* one tick() call,
        a token can land on this machine's receiver from outside, between
        ticks, so the "before" side of the edge has to survive across
        calls to be compared against here).
        """
        if self._currentCommand == TokenDepoCommandKind.STORE_TOKEN:
            self._advance_store_token()
        elif self._currentCommand == TokenDepoCommandKind.EMPTY_RECEIVER:
            self._advance_empty_receiver()

        busy_now = self.receiverSens
        if busy_now and not self._was_receiver_busy:
            self.emit_event_to_factory(TokenDepoMessages.RECEIVER_BUSY)
        elif self._was_receiver_busy and not busy_now:
            self.emit_event_to_factory(TokenDepoMessages.RECEIVER_EMPTY)
        self._was_receiver_busy = busy_now

    def _advance_store_token(self):
        """No-op (beyond stopping) if the receiver's empty -- otherwise
        absorbs the token into tokenCount and removes it from the world.
        Reporting the receiver as free again is tick()'s own edge-check
        job now, not this method's -- see tick()'s docstring.
        """
        token = self._token_at_receiver()
        if token is not None:
            self._factory.remove_token(token)
            self._tokenCount += 1
        self.stop()

    def _advance_empty_receiver(self):
        """No-op (beyond stopping) if the receiver's empty -- otherwise
        ejects the token to whatever machine's footprint the receiver
        lines up with (same drop pattern as
        VacuumGripperMachine.release()). Reporting the receiver as free
        again is tick()'s own edge-check job now -- see tick()'s
        docstring.
        """
        token = self._token_at_receiver()
        if token is not None:
            self._factory.transfer_token(token, self._factory.machine_at(token.position))
        self.stop()

