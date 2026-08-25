import math
import warnings
from dataclasses import dataclass
from typing import Optional

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate, Position3D
from languages.sysmlv2.simulation_models.fischertechnik.enums import ExecutionStatusKind, VacuumGripperCommandKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.movement_computation_model import encoder_changes_per_tick, \
    gripper_tip_position
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
# Round it up to 1890, so that it is easier to be divided by the current max arm extension length model.
MAX_ARM_ENCODER_VALUE: float = 1890.0

# There is also a maximum value for the rotation encoder value
# Based on current data, the actual maximum encoder value is 2986 (for 360 degree)
# To see if we can do the whole 360 degree, then we can calculate what encoder value to get 1 degree increment:
# 2986/360 = 8.2944....
# For now, to show it in the model size, I will make it 8 encoder values for 1 degree. So in total, the maximum
# encoder values for the model size is 8*360 = 2880
MAX_ROT_ENCODER_VALUE: float = 2880.0

# How close a Token's position must be to the gripper tip (each axis) to
# count as "under" it for grip()/release() -- kept independent of
# factory_visualization.py's TOKEN_RADIUS/SCALE (fischertechnik_parts/
# stays visualization-agnostic, same boundary TODAYS-TASKS.md's
# MachineVisualization split already established), so picked as a plain
# model-unit value in the same ballpark as a token's own on-screen
# footprint (TOKEN_RADIUS=8px / SCALE=20 = 0.4 model units).
GRIP_TOLERANCE: float = 0.5

# Chosen so the arm extends/retracts by 0.05 model-size units per tick.
# MAX_ARM_ENCODER_VALUE / MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE (vacuum_gripper.py)
# gives the encoder-units-per-model-unit ratio; 0.05 of that ratio is one
# tick's step. Currently, it is 0.05 * (1890 / 3) = 0.05 * 630 = 31.5
ARM_ENCODER_STEP_PER_TICK: float = 0.05 * (MAX_ARM_ENCODER_VALUE / MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE)

# 0.5 degree per tick (MAX_ROT_ENCODER_VALUE / 360 = 2880.0 / 360 = 8.0,
# vacuum_gripper.py) -- paces goToPosition()/move()/moveToSafePosition()'s
# rotEncoder axis, same role ARM_ENCODER_STEP_PER_TICK plays for armEncoder.
# Literal rather than computed here for the same circular-import reason as
# ARM_ENCODER_STEP_PER_TICK above.
ROT_ENCODER_STEP_PER_TICK: float = (MAX_ROT_ENCODER_VALUE / 360) / 2

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
        self._expectedArmEncoderValue = targetPosition.horizontal
        self._expectedRotationEncoderValue = targetPosition.rot
        self._currentCommand = VacuumGripperCommandKind.GO_TO_POSITION
        self._executionStatus = ExecutionStatusKind.MUST_CONTINUE

    def move(self, startPosition: Position3D, endPosition: Position3D):
        '''
        This method signifies a movement of the gripper's arm from a starting position to an end position.
        If the current encoder values do not match a start position, it is assumed that the movement is canceled,
        and raise a warning. Otherwise, the gripper's arm will be moved to the end position
        :param startPosition: a set of encoder values that specify the starting position of the gripper's arm.
        :param endPosition: a set of encoder values that specify the (target) end position of the gripper's arm
        :return:
        '''
        if self._armEncoder != startPosition.horizontal or self._rotEncoder != startPosition.rot:
            warnings.warn(
                f"move() canceled: current position (armEncoder={self._armEncoder}, "
                f"rotEncoder={self._rotEncoder}) does not match startPosition "
                f"(horizontal={startPosition.horizontal}, rot={startPosition.rot})"
            )
            return

        self._expectedArmEncoderValue = endPosition.horizontal
        self._expectedRotationEncoderValue = endPosition.rot
        self._currentCommand = VacuumGripperCommandKind.MOVE
        self._executionStatus = ExecutionStatusKind.MUST_CONTINUE

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

    def _tip_position(self) -> FactoryCoordinate:
        return gripper_tip_position(
            self._placementCoordinate, self._armEncoder, self._rotEncoder,
            MAX_ARM_ENCODER_VALUE, MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE, MAX_ROT_ENCODER_VALUE,
            DEFAULT_ARM_PIPE_LENGTH,
        )

    def grip(self):
        """
        This method signifies a grip action, where an item is picked at the current arm position described by the current encoder values.
        Such an action described by setting the vacuumActValve and vacuumActCompressorOn attributes to True --
        matches Grip's own `out attribute ... = true` defaults in the SysML model (vgr-cb-true-simulation.xmi),
        set unconditionally regardless of whether anything was actually found to pick up.
        If a Token currently sits under the gripper tip (whichever machine currently owns it, e.g. a belt),
        ownership also transfers to this machine -- the actual physical "pick up". No-op on the token side
        (flags still flip) if nothing is within GRIP_TOLERANCE of the tip.
        :return:
        """
        self._vacuumActValve = True
        self._vacuumActCompressorOn = True

        tip = self._tip_position()
        for token in self._factory.tokens:
            if math.isclose(token.position.x, tip.x, abs_tol=GRIP_TOLERANCE) and \
                    math.isclose(token.position.y, tip.y, abs_tol=GRIP_TOLERANCE):
                self._factory.transfer_token(token, self)
                break

    def release(self):
        """
        This method signifies a release action, where an item is released at the current arm position described by the current encoder values.
        Such an action described by setting the vacuumActValve and vacuumActCompressorOn attributes to False.
        Any Token currently held by this machine is dropped at the gripper tip's current position -- ownership
        transfers to whatever machine's footprint the tip is over (e.g. a ConveyorBeltMachine it lines up with,
        via Factory.machine_at()), or becomes unowned if nothing claims that spot.
        :return:
        """
        self._vacuumActValve = False
        self._vacuumActCompressorOn = False

        tip = self._tip_position()
        for token in self._factory.tokens_on(self):
            token.move_to(tip)
            self._factory.transfer_token(token, self._factory.machine_at(tip))

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
        self._expectedArmEncoderValue = 0.0
        self._expectedRotationEncoderValue = 0.0
        self._currentCommand = VacuumGripperCommandKind.MOVE_TO_SAFE_POSITION
        self._executionStatus = ExecutionStatusKind.MUST_CONTINUE

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

    def extendArm(self):
        """
        This method does not exist in the HMI command of Fischertechnik platform. The purpose of this method
        is to show the arm can be extended.
        :return:
        """
        self._expectedArmEncoderValue = MAX_ARM_ENCODER_VALUE
        self._currentCommand = VacuumGripperCommandKind.EXTEND_ARM
        self._executionStatus = ExecutionStatusKind.MUST_CONTINUE

    def tick(self) -> None:
        if self._currentCommand in [VacuumGripperCommandKind.RETRACT_ARM, VacuumGripperCommandKind.EXTEND_ARM]:
            self._advance_or_retract_arm()
        elif self._currentCommand in [VacuumGripperCommandKind.GO_TO_POSITION, VacuumGripperCommandKind.MOVE]:
            self._advance_go_to_position()
        elif self._currentCommand == VacuumGripperCommandKind.MOVE_TO_SAFE_POSITION:
            self._advance_move_to_safe_position()
        self._carry_held_token()

    def _carry_held_token(self):
        """Keeps any Token currently held by this machine glued to the
        gripper tip -- called unconditionally at the end of every tick()
        (after whichever _advance_* just moved the encoders this tick),
        so a held token tracks the tip through RETRACT_ARM/EXTEND_ARM
        (armEncoder only) and GO_TO_POSITION/MOVE/MOVE_TO_SAFE_POSITION
        (both axes) alike, without each of those needing its own copy of
        this logic. Mirrors ConveyorBeltMachine's own
        _move_owned_tokens_one_step(), just against the tip position
        instead of a belt step.
        """
        tip = self._tip_position()
        for token in self._factory.tokens_on(self):
            token.move_to(tip)

    def _advance_or_retract_arm(self):
        self._armEncoder = encoder_changes_per_tick(self._armEncoder, self._expectedArmEncoderValue,
                                                    ARM_ENCODER_STEP_PER_TICK)
        if self._armEncoder == self._expectedArmEncoderValue:
            self.stop()

    def _advance_arm_and_rotation(self) -> bool:
        """Steps armEncoder/rotEncoder one tick each toward their expected
        values; returns True once both have arrived. Shared by
        goToPosition/move (stop once arrived) and moveToSafePosition
        (also release the vacuum once arrived) -- both GO_TO_POSITION and
        MOVE drive the exact same two axes toward whatever
        expectedArmEncoderValue/expectedRotationEncoderValue currently
        holds, the only difference between them being how those got set
        (goToPosition() takes a target directly; move() validates against
        startPosition first).
        """
        self._armEncoder = encoder_changes_per_tick(self._armEncoder, self._expectedArmEncoderValue,
                                                      ARM_ENCODER_STEP_PER_TICK)
        self._rotEncoder = encoder_changes_per_tick(self._rotEncoder, self._expectedRotationEncoderValue,
                                                      ROT_ENCODER_STEP_PER_TICK)
        return self._armEncoder == self._expectedArmEncoderValue and self._rotEncoder == self._expectedRotationEncoderValue

    def _advance_go_to_position(self):
        if self._advance_arm_and_rotation():
            self.stop()

    def _advance_move_to_safe_position(self):
        if self._advance_arm_and_rotation():
            self.release()
            self.stop()