import math

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import DirectionKind

# Chosen so the arm extends/retracts by 0.01 model-size units per tick.
# MAX_ARM_ENCODER_VALUE / MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE (vacuum_gripper.py)
# gives the encoder-units-per-model-unit ratio; 0.01 of that ratio is one
# tick's step:
#   step = 0.01 * (MAX_ARM_ENCODER_VALUE / MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE)
#        = 0.01 * (1890.0 / 3.0)
#        = 0.01 * 630.0
#        = 6.3
# Hardcoded rather than computed from those two constants directly: both
# live in vacuum_gripper.py, which already imports this module, so
# importing them back here would be circular. Update this by hand if
# either constant changes.
ARM_ENCODER_STEP_PER_TICK: float = 6.3

# 1 degree per tick (MAX_ROT_ENCODER_VALUE / 360 = 2880.0 / 360 = 8.0,
# vacuum_gripper.py) -- paces goToPosition()/move()/moveToSafePosition()'s
# rotEncoder axis, same role ARM_ENCODER_STEP_PER_TICK plays for armEncoder.
# Literal rather than computed here for the same circular-import reason as
# ARM_ENCODER_STEP_PER_TICK above.
ROT_ENCODER_STEP_PER_TICK: float = 8.0

# Matches the gripper arm's own visual pace (ARM_ENCODER_STEP_PER_TICK
# above works out to 0.01 model-size units/tick via arm_encoder_to_model_size)
# so a belt token and the gripper's arm read as moving at the same speed
# on screen, instead of one covering ground faster than the other.
CB_STEP_SIZE_PER_TICK: float = 0.01

def rotate_offset(offset: float, degrees: int) -> tuple[float, float]:
    """(dx, dy) of a vector of length `offset` along local +x, rotated by
    `degrees` -- the shared primitive behind both a belt's fixed feed/swap
    endpoints and its per-tick step direction.
    """
    theta = math.radians(degrees)
    return offset * math.cos(theta), offset * math.sin(theta)


def cb_step_position(current: FactoryCoordinate, degrees: int, direction: DirectionKind, step_size: float = CB_STEP_SIZE_PER_TICK) -> FactoryCoordinate:
    """One tick's worth of movement from `current`: `step_size` model
    units along the axis defined by `degrees` -- toward local +x for
    FORWARD, local -x for BACKWARD. Continuous (no rounding) -- a token's
    position accumulates in `step_size` increments exactly, so callers
    that need to know "did this arrive at some fixed point" (e.g. a
    belt's feed/swap sensors) must compare with a tolerance rather than
    exact equality, since float addition doesn't guarantee landing
    exactly on a target even when step_size evenly divides the distance
    to it in exact arithmetic.
    """
    sign = 1 if direction == DirectionKind.FORWARD else -1
    dx, dy = rotate_offset(sign * step_size, degrees)
    return FactoryCoordinate(current.x + dx, current.y + dy, current.degrees)


def arm_encoder_to_model_size(arm_encoder: float, max_arm_encoder_value: float, max_arm_extension_length: float) -> float:
    """Linear ticks -> model-distance conversion: `arm_encoder` (0..
    max_arm_encoder_value) maps proportionally onto 0..
    max_arm_extension_length -- how far past DEFAULT_ARM_PIPE_LENGTH the
    extendable rod currently reaches (VacuumGripperVisualization.draw()).
    Takes both max values as parameters rather than importing
    MAX_ARM_ENCODER_VALUE/MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE from
    vacuum_gripper.py directly -- that module already imports this one,
    so importing back would be circular, same reasoning as
    ARM_ENCODER_STEP_PER_TICK above.
    """
    return arm_encoder / max_arm_encoder_value * max_arm_extension_length

def rot_encoder_to_degrees(rot_encoder: float, max_rot_encoder_value: float) -> float:
    """Linear ticks -> degrees conversion: `rot_encoder` (0..
    max_rot_encoder_value) maps proportionally onto 0..360 degrees -- how
    far the arm has swiveled around the tower
    (VacuumGripperVisualization.draw()). Takes max_rot_encoder_value as a
    parameter rather than importing MAX_ROT_ENCODER_VALUE from
    vacuum_gripper.py directly, same circular-import reasoning as
    arm_encoder_to_model_size above. Previously named
    rot_encoder_to_model_size -- renamed since a rotation isn't a "model
    size"; nothing called it under the old name yet (it was still an
    empty stub), so this is a pure rename, not a breaking change.
    """
    return rot_encoder / max_rot_encoder_value * 360.0

def gripper_tip_position(placement: FactoryCoordinate, arm_encoder: float, rot_encoder: float,
                          max_arm_encoder_value: float, max_arm_extension_length: float,
                          max_rot_encoder_value: float, default_arm_pipe_length: float) -> FactoryCoordinate:
    """Model-space FactoryCoordinate of the gripper's tip right now --
    the same geometry VacuumGripperVisualization.draw() renders (fixed
    pipe + live extension along local +x, swiveled by rotEncoder, then
    carried by the machine's own placementCoordinate) -- computed fresh
    here rather than read off a stored attribute, so grip()/release() can
    never see it go stale relative to armEncoder/rotEncoder/
    placementCoordinate. Same reasoning as ConveyorBeltMachine's
    conveyorSensFeed/conveyorSensSwap being computed @property, not
    cached fields, and the same rotate_offset() primitive
    ConveyorBeltMachine._end_position() uses for its own fixed points.
    Takes every max_*/default_arm_pipe_length value as a parameter rather
    than importing it from vacuum_gripper.py directly, same
    circular-import reasoning as arm_encoder_to_model_size/
    rot_encoder_to_degrees above.
    """
    extension = arm_encoder_to_model_size(arm_encoder, max_arm_encoder_value, max_arm_extension_length)
    local_x = default_arm_pipe_length + extension
    degrees = placement.degrees + rot_encoder_to_degrees(rot_encoder, max_rot_encoder_value)
    dx, dy = rotate_offset(local_x, degrees)
    return FactoryCoordinate(placement.x + dx, placement.y + dy, degrees)


def encoder_changes_per_tick(current: float, target: float, step: float) -> float:
    """Moves `current` at most `step` closer to `target`, clamped so it
    never overshoots -- lands exactly on `target` once within one step of
    it. Shared by every encoder axis's `_advance_*` method in tick().
    """
    if current < target:
        return min(current + step, target)
    if current > target:
        return max(current - step, target)
    return current