from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate


class Token:

    def __init__(self, token_id: str, position: FactoryCoordinate):
        self._token_id = token_id
        self._position = position

    @property
    def token_id(self):
        return self._token_id

    @property
    def position(self):
        return self._position

    def move_to(self, position: FactoryCoordinate):
        """Only place a Token's position is ever mutated. Machine action
        methods (e.g. ConveyorBeltMachine.moveToSensor) call this instead of
        assigning a new position directly, so a later switch to interpolated/
        animated motion only needs to change this one method's body.
        """
        self._position = position

    def __repr__(self):
        return f"Token({self._token_id!r}, x={self._position.x}, y={self._position.y})"
