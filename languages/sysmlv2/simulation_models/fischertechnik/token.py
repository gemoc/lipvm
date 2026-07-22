from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import TokenColorKind


class Token:

    def __init__(self, token_id: str, position: FactoryCoordinate, color: TokenColorKind):
        self._token_id = token_id
        self._position = position
        self._color = color

    @property
    def token_id(self):
        return self._token_id

    @property
    def position(self):
        return self._position

    @property
    def color(self):
        return self._color

    def move_to(self, position: FactoryCoordinate):
        """Only place a Token's position is ever mutated. Machine action
        methods (e.g. ConveyorBeltMachine.moveToSensor) call this instead of
        assigning a new position directly, so a later switch to interpolated/
        animated motion only needs to change this one method's body.
        """
        self._position = position

    def __repr__(self):
        return f"Token({self._token_id!r}, x={self._position.x}, y={self._position.y}, color={self._color.name})"
