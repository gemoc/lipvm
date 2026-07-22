class FactoryCoordinate:

    def __init__(self, x: int, y: int, degrees: int):
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