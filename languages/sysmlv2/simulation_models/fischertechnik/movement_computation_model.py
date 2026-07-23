import math

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import DirectionKind

def rotate_offset(offset: float, degrees: int) -> tuple[float, float]:
    """(dx, dy) of a vector of length `offset` along local +x, rotated by
    `degrees` -- the shared primitive behind both a belt's fixed feed/swap
    endpoints and its per-tick step direction.
    """
    theta = math.radians(degrees)
    return offset * math.cos(theta), offset * math.sin(theta)


def cb_step_position(current: FactoryCoordinate, degrees: int, direction: DirectionKind, step_size: int = 1) -> FactoryCoordinate:
    """One tick's worth of movement from `current`: `step_size` model
    units along the axis defined by `degrees` -- toward local +x for
    FORWARD, local -x for BACKWARD. Rounded to the nearest grid cell since
    FactoryCoordinate is integer-only -- exact for 0/90/180/270 degrees.
    """
    sign = 1 if direction == DirectionKind.FORWARD else -1
    dx, dy = rotate_offset(sign * step_size, degrees)
    return FactoryCoordinate(round(current.x + dx), round(current.y + dy), current.degrees)