from dataclasses import dataclass
from typing import Optional

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import TokenDepoCommandKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.movement_computation_model import rotate_offset
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
        self._receiverSens: bool = False
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
        return self._receiverSens

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
        """STOP is this machine's own idle sentinel (not None -- see
        __init__/stop()), same override ConveyorBeltMachine/
        VacuumGripperMachine need for the same reason.
        """
        return self._currentCommand == TokenDepoCommandKind.STOP

    def tick(self) -> None:
        """No behavior wired up yet -- see this module's own "dummy
        machine" comment. Still required: PartSimulationModel.tick() is
        abstract, so without this override the class couldn't even be
        instantiated.
        """
        pass

