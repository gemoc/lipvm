from dataclasses import dataclass
from typing import Optional

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import TokenProducerCommandKind, TokenColorKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.movement_computation_model import rotate_offset
from languages.sysmlv2.simulation_models.generic import PartSimulationModel

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

@dataclass(frozen=True)
class TokenProducerMachineSnapshot:
    currentCommand: Optional[TokenProducerCommandKind]
    lastUsedTokenColor: Optional[TokenColorKind]
    placementCoordinate: FactoryCoordinate

class TokenProducerMachine(PartSimulationModel):

    snapshot_type = TokenProducerMachineSnapshot

    def __init__(self, factory: Factory):

        super().__init__()

        self._currentCommand: TokenProducerCommandKind = TokenProducerCommandKind.STOP
        self._lastUsedTokenColor: Optional[TokenColorKind] = None
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
        """STOP is this machine's own idle sentinel (not None -- see
        __init__/stop()), same override ConveyorBeltMachine/
        VacuumGripperMachine need for the same reason.
        """
        return self._currentCommand == TokenProducerCommandKind.STOP

    def tick(self) -> None:
        """No behavior wired up yet -- see this module's own "dummy
        machine" comment. Still required: PartSimulationModel.tick() is
        abstract, so without this override the class couldn't even be
        instantiated.
        """
        pass

