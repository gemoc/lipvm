import math

from languages.sysmlv2.simulation_models.fischertechnik.enums import DirectionKind
from languages.sysmlv2.simulation_models.generic import CustomAttributeModel


class FactoryCoordinate(CustomAttributeModel):

    def __init__(self, x: float, y: float, degrees: float = 0.0):
        self._x = x
        self._y = y
        self._degrees = degrees

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def degrees(self):
        return self._degrees
