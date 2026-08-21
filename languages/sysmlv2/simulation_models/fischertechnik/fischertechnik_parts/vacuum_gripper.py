from dataclasses import dataclass
from typing import Optional

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate, Position3D
from languages.sysmlv2.simulation_models.fischertechnik.enums import ExecutionStatusKind, VacuumGripperCommandKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.generic import PartSimulationModel


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
        pass

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
        This signifies a movement to fully retract the arm. To achieve this, we need the vertical and arm encoder values
        to be 0
        :return:
        """
        pass

    def tick(self) -> None:
        pass