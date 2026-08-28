import math
from dataclasses import dataclass
from enum import Enum

from languages.sysmlv2.simulation_models.fischertechnik import factory
from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import DirectionKind, ConveyorCommandKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts.conveyor_belt import CB_WIDTH
from languages.sysmlv2.simulation_models.fischertechnik.machine import FischertechnikMachine
from languages.sysmlv2.simulation_models.fischertechnik.movement_computation_model import rotate_offset, cb_step_position

# The belt's own physical housing, the length is 27.5cm and width is 6cm
# In model size, the length would be 5.5 and width is 1.1
SL_LENGTH: float = 7.6
SL_WIDTH: float = 4
BELT_WIDTH: float = CB_WIDTH

PISTON_WIDTH: float = 1.8
SORTED_TOKEN_PLATFORM_WIDTH: float = 1.1

#There is a tolerance gap of 5 cm on either end, where it is the placement for the sensor
END_OF_SL_TOLERANCE: float = 1.0

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

        self._sensor_SL_in: bool = False
        self._sensor_SL_blue: bool = False
        self._sensor_SL_white: bool = False
        self._sensor_SL_red: bool = False

        self._placementCoordinate : FactoryCoordinate = None

    @property
    def sensor_SL_in(self):
        return self._sensor_SL_in

    @property
    def sensor_SL_blue(self):
        return self._sensor_SL_blue

    @property
    def sensor_SL_white(self):
        return self._sensor_SL_white

    @property
    def sensor_SL_red(self):
        return self._sensor_SL_red

    @property
    def placementCoordinate(self):
        return self._placementCoordinate

    @placementCoordinate.setter
    def placementCoordinate(self, value):
        self._placementCoordinate = value

    def eject(self):

        pass

    def stop(self):

        pass

    def is_idle(self) -> bool:

        return False

    def tick(self) -> None:

        pass