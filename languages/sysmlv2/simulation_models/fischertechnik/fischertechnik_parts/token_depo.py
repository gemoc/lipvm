import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import TokenDepoCommandKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.machine import FischertechnikMachine
from languages.sysmlv2.simulation_models.fischertechnik.movement_computation_model import rotate_offset
from languages.sysmlv2.simulation_models.fischertechnik.token import Token

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

class TokenDepoMachine(FischertechnikMachine):

    snapshot_type = TokenDepoMachineSnapshot

    def __init__(self, factory: Factory):
        super().__init__(factory)

        self._currentCommand: TokenDepoCommandKind = TokenDepoCommandKind.STOP
        self._tokenCount: int = 0
        self._placementCoordinate: FactoryCoordinate = None

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
        if the receiver is empty.
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
        own local +x axis, rotated by placementCoordinate.degrees.
        """
        dx, dy = rotate_offset(TOKEN_RECEIVER_OFFSET, self._placementCoordinate.degrees)
        return FactoryCoordinate(
            self._placementCoordinate.x + dx,
            self._placementCoordinate.y + dy,
            self._placementCoordinate.degrees,
        )

    def contains_position(self, position: FactoryCoordinate) -> bool:
        """Whether `position` is close enough to receiver_position() to
        count as landing on this machine's receiver platform -- lets
        VacuumGripperMachine.release() (via Factory.machine_at()) hand a
        released token's ownership to this machine, instead of it going
        unowned.
        """
        receiver = self.receiver_position()
        return math.isclose(position.x, receiver.x, abs_tol=RECEIVER_ARRIVAL_TOLERANCE) and \
               math.isclose(position.y, receiver.y, abs_tol=RECEIVER_ARRIVAL_TOLERANCE)

    def is_idle(self) -> bool:
        """Always False, because this machine must be monitored every tick, especially
        to ensure we can check whether there is a token or not
        """
        return False

    def storeToken(self):
        """
        This method allows the token that is currently placed in the receiver platform
        to be stored inside the machine. If there is no token in the receiver, then this
        method will do nothing.
        :return:
        """
        self._currentCommand = TokenDepoCommandKind.STORE_TOKEN

    def emptyReceiver(self):
        """
        This method ejects the token that is currently placed in the receiver platform. If
        there is no token in the receiver, then this method will do nothing.
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

    def tick(self) -> None:
        """Dispatches to whichever _advance_* method matches
        currentCommand (a no-op when it's STOP -- there's nothing to
        advance), then checks receiverSens for an edge transition via
        FischertechnikMachine._sensor_edge().
        """
        if self._currentCommand == TokenDepoCommandKind.STORE_TOKEN:
            self._advance_store_token()
        elif self._currentCommand == TokenDepoCommandKind.EMPTY_RECEIVER:
            self._advance_empty_receiver()

        edge = self._sensor_edge('receiverSens', self.receiverSens)
        if edge is True:
            self.emit_event_to_factory(TokenDepoMessages.RECEIVER_BUSY)
        elif edge is False:
            self.emit_event_to_factory(TokenDepoMessages.RECEIVER_EMPTY)

    def _advance_store_token(self):
        """No-op (beyond stopping) if the receiver's empty -- otherwise
        absorbs the token into tokenCount and removes it from the world.
        """
        token = self._token_at_receiver()
        if token is not None:
            self._factory.remove_token(token)
            self._tokenCount += 1
        self.stop()

    def _advance_empty_receiver(self):
        """No-op (beyond stopping) if the receiver's empty -- otherwise
        ejects the token from the simulation altogether.
        """
        token = self._token_at_receiver()
        if token is not None:
            self._factory.remove_token(token)
        self.stop()

