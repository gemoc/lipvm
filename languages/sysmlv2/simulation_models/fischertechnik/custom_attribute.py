from languages.sysmlv2.simulation_models.generic import CustomAttributeModel


class FactoryCoordinate(CustomAttributeModel):

    def __init__(self, x: float, y: float, degrees: float = 0.0):

        """
        :param x: the x coordinate of machines or tokens in the visualization
        :param y: the y coordinate of machines or tokens in the visualization
        :param degrees: clockwise angle of machines or tokens in the visualization
        """
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

class Position3D(CustomAttributeModel):

    def __init__(self, vertical:float, horizontal:float, rot:float):

        self._vertical = vertical
        self._horizontal = horizontal
        self._rot = rot

    @property
    def vertical(self):
        return self._vertical

    @property
    def horizontal(self):
        return self._horizontal

    @property
    def rot(self):
        return self._rot