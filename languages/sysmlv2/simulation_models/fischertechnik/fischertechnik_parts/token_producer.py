from dataclasses import dataclass
from typing import Optional

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import TokenProducerCommandKind, TokenColorKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.generic import PartSimulationModel


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

    def is_idle(self) -> bool:
        """STOP is this machine's own idle sentinel (not None -- see
        __init__/stop()), same override ConveyorBeltMachine/
        VacuumGripperMachine need for the same reason.
        """
        return self._currentCommand == TokenProducerCommandKind.STOP

