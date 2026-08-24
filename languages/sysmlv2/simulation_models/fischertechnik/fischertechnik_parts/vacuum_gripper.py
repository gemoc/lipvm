from dataclasses import dataclass
from typing import Optional

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate, Position3D
from languages.sysmlv2.simulation_models.fischertechnik.enums import ExecutionStatusKind, VacuumGripperCommandKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.generic import PartSimulationModel

# At the base of the VGR, there is a square with length 25.5 cm and width 18.5 cm that we cannot use
# With the model size, let's divide it up into 5, which yields length 5.1 and width 3.7
VGR_BASE_LENGTH: float = 5.1
VGR_BASE_WIDTH: float = 3.7

# There is also a dimension to the `tower` which held the arm. This tower has a base of 10 cm and width 7 cm
# With the model size, let's divide it up into 5, which yields length 2 and width 1.4
VGR_TOWER_BASE_LENGTH: float = 2.0
VGR_TOWER_BASE_WIDTH: float = 1.4

# From center to the start of the arm is 12.2 cm (+- 0.5 cm).
# Let's round it up to 13, taking the account that we add 0.5 cm.
# With the model size, let's divide it up into 5, which yields 2.6
DEFAULT_ARM_PIPE_LENGTH: float = 2.6

# The gripper's arm held inside the gripper pipe can be extended/
# In real life, the maximum arm extension length is 15.2 cm -> round it up to 15
# With the model size, let's divide it up into 5, which yields 3.0
MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE: float = 3.0

# The gripper's arm max encoder value (To fully extend the arm) which would be 1881
# Round it up to 1880. However, when looking at the max extension length in terms of model size
# Dividing 3.0 into 1880 is too much. Thus, I am using 240 for now
MAX_ARM_ENCODER_VALUE: float = 1880.0

# There is also a maximum value for the rotation encoder value
# Based on current data, the actual maximum encoder value is 2986 (for 360 degree)
# To see if we can do the whole 360 degree, then we can calculate what encoder value to get 1 degree increment:
# 2986/360 = 8.2944....
# For now, to show it in the model size, I will make it 8 encoder values for 1 degree. So in total, the maximum
# encoder values for the model size is 8*360 = 2880
MAX_ROT_ENCODER_VALUE: float = 2880.0

@dataclass(frozen=True)
class VacuumGripperMachineSnapshot:
    currentCommand: Optional[VacuumGripperCommandKind]
    executionStatus: Optional[ExecutionStatusKind]

    verticalEncoder: float
    armEncoder: float
    rotEncoder: float

    expectedVerticalEncoderValue: float
    expectedArmEncoderValue: float
    expectedRotationEncoderValue: float

    vacuumActCompressorOn: bool
    vacuumActValve: bool

    placementCoordinate: FactoryCoordinate


class VacuumGripperMachine(PartSimulationModel):

    snapshot_type = VacuumGripperMachineSnapshot

    def __init__(self, factory: Factory):
        super().__init__()

        self._factory = factory

        self._currentCommand: Optional[VacuumGripperCommandKind] = None
        self._executionStatus: Optional[ExecutionStatusKind] = None

        self._verticalEncoder: float= 0.0
        self._armEncoder: float= 0.0
        self._rotEncoder: float= 0.0

        self._expectedVerticalEncoderValue: float = 0.0
        self._expectedArmEncoderValue: float = 0.0
        self._expectedRotationEncoderValue: float= 0.0

        self._vacuumActCompressorOn: bool = False
        self._vacuumActValve: bool = False
        self._placementCoordinate : FactoryCoordinate = None

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
    def executionStatus(self):
        return self._executionStatus

    @property
    def verticalEncoder(self):
        return self._verticalEncoder

    @property
    def armEncoder(self):
        return self._armEncoder

    @property
    def rotEncoder(self):
        return self._rotEncoder

    @property
    def expectedVerticalEncoderValue(self):
        return self._expectedVerticalEncoderValue

    @property
    def expectedArmEncoderValue(self):
        return self._expectedArmEncoderValue

    @property
    def expectedRotationEncoderValue(self):
        return self._expectedRotationEncoderValue

    @property
    def vacuumActCompressorOn(self):
        return self._vacuumActCompressorOn

    @property
    def vacuumActValve(self):
        return self._vacuumActValve

    def goToPosition(self, targetPosition: Position3D):
        '''
        This method signifies a movement of the gripper's arm to a particular position.
        As the first step, this would calculate how to reach the target position from
        the current encoder values (i.e., verticalEncoder, armEncoder, rotEncoder). This calculation then will
        set the expected encoder values, set the value of currentCommand attribute, and executionStatus become MUST_CONTINUE.
        :param targetPosition:
        '''
        pass

    def move(self, startPosition: Position3D, endPosition: Position3D):
        pass

    def pick(self, targetPosition: Position3D):
        '''
        This method signifies a compound movement, where a gripper's arm is moved to a particular position and
        then pick object that exists in this position. To describe this compound, it would use the goToPosition method
        and then grip method.
        :param targetPosition:
        '''
        pass

    def place(self, targetPosition: Position3D):
        pass

    def grip(self):
        """
        This method signifies a grip action, where an item is picked at the current arm position described by the current encoder values.
        Such an action described by setting the vacuumActValve and vacuumActCompressorOn attributes to True.
        :return:
        """
        pass

    def release(self):
        """
        This method signifies a release action, where an item is released at the current arm position described by the current encoder values.
        Such an action described by setting the vacuumActValve and vacuumActCompressorOn attributes to True.
        :return:
        """
        pass

    def stop(self):
        """
        This method stops any action performed by the gripper. Basically, just set the value of currentCommand and
        executionStatus attributes to None
        :return:
        """
        self._currentCommand = None
        self._executionStatus = None

    def moveToSafePosition(self):
        """
        This signifies a movement of the gripper's arm to a safe position and releasing. Safe position means that
        all encoder values are 0, and the vacuumActValve and vacuumActCompressorOn attributes are False.
        executionStatus attributes to None
        :return:
        """
        pass

    def retractArm(self):
        """
        This signifies a movement to fully retract the arm. To achieve this, we need the arm encoder values to be 0
        :return:
        """
        self._expectedArmEncoderValue = 0.0
        self._currentCommand = VacuumGripperCommandKind.RETRACT_ARM
        self._executionStatus = ExecutionStatusKind.MUST_CONTINUE

    def setup(self):

        pass

    def tick(self) -> None:
        if self._currentCommand == VacuumGripperCommandKind.RETRACT_ARM:
            self._advance_retract_arm()

    def _advance_retract_arm(self):
        self._armEncoder = _step_toward(self._armEncoder, self._expectedArmEncoderValue, ARM_ENCODER_STEP_PER_TICK)
        if self._armEncoder == self._expectedArmEncoderValue:
            self.stop()