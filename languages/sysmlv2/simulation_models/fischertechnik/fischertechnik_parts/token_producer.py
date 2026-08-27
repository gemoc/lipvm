import math
import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import TokenProducerCommandKind, TokenColorKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.machine import FischertechnikMachine
from languages.sysmlv2.simulation_models.fischertechnik.movement_computation_model import rotate_offset
from languages.sysmlv2.simulation_models.fischertechnik.token import Token

# This is a dummy machine. Thus, we can make our own model size
TOKEN_PROD_BASE_LENGTH = 3
TOKEN_PROD_BASE_WIDTH = 3
TOKEN_PLATFORM_LENGTH = 1.5
TOKEN_PLATFORM_WIDTH = 1.5

# Model-unit distance from the machine's own center to the platform's
# center, along its local +x axis (the base's right edge, then half the
# platform's own length past it) -- the single offset both
# platform_position() and TokenProducerVisualization.draw() build from,
# so the drawn platform and wherever a produced token actually appears
# can never drift apart, same reasoning ConveyorBeltMachine's
# FEED_TO_SWAP_LENGTH drives both _end_position() and its visualization.
TOKEN_PLATFORM_OFFSET = TOKEN_PROD_BASE_LENGTH / 2 + TOKEN_PLATFORM_LENGTH / 2

# A token within this distance of platform_position() counts as "on" the
# platform -- same reasoning as TokenDepoMachine's own
# RECEIVER_ARRIVAL_TOLERANCE (token_depo.py).
PLATFORM_ARRIVAL_TOLERANCE = min(TOKEN_PLATFORM_LENGTH, TOKEN_PLATFORM_WIDTH) / 2

@dataclass(frozen=True)
class TokenProducerMachineSnapshot:
    currentCommand: Optional[TokenProducerCommandKind]
    lastUsedTokenColor: Optional[TokenColorKind]
    placementCoordinate: FactoryCoordinate
    platformSens: bool

class TokenProducerMessages(Enum):
    SUCCESS_MESSAGE = 'TokenProducerSuccessEventMessage'
    PLATFORM_BUSY = 'TokenPlatformBusyEventMessage'
    PLATFORM_EMPTY = 'TokenPlatformFreeEventMessage'

class TokenProducerMachine(FischertechnikMachine):

    snapshot_type = TokenProducerMachineSnapshot

    def __init__(self, factory: Factory):

        super().__init__(factory)
        self._currentCommand: TokenProducerCommandKind = TokenProducerCommandKind.STOP
        self._lastUsedTokenColor: Optional[TokenColorKind] = None
        self._placementCoordinate: FactoryCoordinate = None

    @property
    def platformSens(self):
        return self._token_at_platform() is not None

    def _token_at_platform(self) -> Optional[Token]:
        """The Token currently owned by this machine that sits at
        platform_position() (within PLATFORM_ARRIVAL_TOLERANCE), or None
        if the platform is empty. Same ownership-gated shape as
        TokenDepoMachine._token_at_receiver().
        """
        platform = self.platform_position()
        for token in self._factory.tokens_on(self):
            if math.isclose(token.position.x, platform.x, abs_tol=PLATFORM_ARRIVAL_TOLERANCE) and \
                    math.isclose(token.position.y, platform.y, abs_tol=PLATFORM_ARRIVAL_TOLERANCE):
                return token
        return None

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
    def lastUsedTokenColor(self):
        return self._lastUsedTokenColor

    def platform_position(self) -> FactoryCoordinate:
        """Coordinate of the platform a produced token is placed on --
        TOKEN_PLATFORM_OFFSET model units along the machine's own local
        +x axis, rotated by placementCoordinate.degrees. Same fixed-
        reference-point shape as ConveyorBeltMachine._end_position()'s
        feed_position()/swap_position().
        """
        dx, dy = rotate_offset(TOKEN_PLATFORM_OFFSET, self._placementCoordinate.degrees)
        return FactoryCoordinate(
            self._placementCoordinate.x + dx,
            self._placementCoordinate.y + dy,
            self._placementCoordinate.degrees,
        )

    def is_idle(self) -> bool:
        """Always False -- This machine has to keep
        scanning platformSens every tick regardless of whether a command
        is currently running.
        """
        return False

    def emitToken(self, desiredColor: TokenColorKind):
        """
        This method allow a token to be produced according to the desired color.
        The produced token will be placed on the platform.
        :param desiredColor: The produced token's color
        :return:
        """
        self._currentCommand = TokenProducerCommandKind.EMIT_TOKEN
        self._lastUsedTokenColor = desiredColor

    def randomEmitToken(self):
        """
        This method allow a token to be produced, albeit the token's color is determined
        randomly. The produced token will be placed on the platform.
        :return:
        """
        self._currentCommand = TokenProducerCommandKind.RANDOM_EMIT_TOKEN

    def emptyPlatform(self):
        """
        Drop the token that is currently placed in the platform.
        :return:
        """
        self._currentCommand = TokenProducerCommandKind.EMPTY_PLATFORM

    def stop(self):
        """
        Stop the token producer machine
        :return:
        """
        self._currentCommand = TokenProducerCommandKind.STOP
        self.emit_event_to_factory(TokenProducerMessages.SUCCESS_MESSAGE)

    def tick(self) -> None:
        """Dispatches to whichever _advance_* method matches
        currentCommand (a no-op when it's STOP -- there's nothing to
        advance), then checks platformSens for an edge transition via
        FischertechnikMachine._sensor_edge() -- same reasoning as
        TokenDepoMachine.tick(): a token can leave this platform from
        outside this machine's own command (see is_idle()'s docstring),
        so the "before" state has to survive across ticks rather than
        being captured locally within one call.
        """
        if self._currentCommand == TokenProducerCommandKind.EMIT_TOKEN:
            self._emit_token(self._lastUsedTokenColor)
        elif self._currentCommand == TokenProducerCommandKind.RANDOM_EMIT_TOKEN:
            self._lastUsedTokenColor = random.choice(list(TokenColorKind))
            self._emit_token(self._lastUsedTokenColor)
        elif self._currentCommand == TokenProducerCommandKind.EMPTY_PLATFORM:
            self._advance_empty_platform()

        edge = self._sensor_edge('platformSens', self.platformSens)
        if edge is True:
            self.emit_event_to_factory(TokenProducerMessages.PLATFORM_BUSY)
        elif edge is False:
            self.emit_event_to_factory(TokenProducerMessages.PLATFORM_EMPTY)

    def _emit_token(self, color: TokenColorKind) -> None:
        """If the platform's already occupied, can't place a second token on top of one already there without
        orphaning it. Otherwise, spawns a new Token of `color` at
        platform_position(), owned by this machine.
        """
        if not self.platformSens:
            self._factory.spawn_token(self.platform_position(), color, self)
        self.stop()

    def _advance_empty_platform(self):
        """No-op (beyond stopping) if the platform's empty -- otherwise
        ejects the token to whatever machine's footprint the platform
        lines up with (same drop pattern as
        TokenDepoMachine._advance_empty_receiver()/
        VacuumGripperMachine.release()).
        """
        token = self._token_at_platform()
        if token is not None:
            self._factory.transfer_token(token, self._factory.machine_at(token.position))
        self.stop()

