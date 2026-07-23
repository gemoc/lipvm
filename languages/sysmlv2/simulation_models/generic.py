from abc import ABC, abstractmethod

class ActionSimulationModel(ABC):

    @abstractmethod
    def evaluate(self):
        raise NotImplementedError("Sub-class must implement this method.")

class PartSimulationModel(ABC):
    """Shared base for every simulated part (ConveyorBeltMachine, and any
    future machine kind in any domain, e.g. water_power_plant). Carries a
    `name` -- a plain, opaque identifier this class doesn't interpret in
    any way itself; a caller (e.g. FischertechnikBridge, using a SysML
    qualified name) decides what it means and sets it. Factory keys its
    machine registry by this name, so it must be set to something unique
    before a subclass instance is registered.
    """

    def __init__(self):
        self._name = None

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

class Print(ActionSimulationModel):

    def __init__(self, msg):
        self.msg = msg

    def evaluate(self):
        print(self.msg)

