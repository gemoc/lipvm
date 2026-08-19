import dataclasses
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

    Also provides `snapshot()` (see TODAYS-TASKS.md's published-snapshot
    design) -- domain-agnostic on purpose, same reasoning as
    facade_proxy.py's `SimulationBridge`: the *mechanism* (reflect over a
    dataclass's declared fields, pull each one off `self`) doesn't need to
    know what attributes any particular machine kind has, so generalizing
    it here isn't speculating about a domain that doesn't exist yet --
    only the domain-specific `snapshot_type` a subclass points at is.
    """

    snapshot_type: type = None  # subclass sets this to its own frozen dataclass (e.g. ConveyorBeltMachineSnapshot)

    def __init__(self):
        self._name = None

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    def snapshot(self):
        """Builds this instance's `snapshot_type` by reflecting over that
        dataclass's own declared fields and pulling each one off `self` via
        getattr -- so a subclass lists its attribute names exactly once (in
        its `snapshot_type` dataclass), never a second time here. A field
        declared on `snapshot_type` with no matching attribute on `self`
        fails loudly (AttributeError) the moment this is called, rather
        than silently producing a stale or wrong snapshot.
        """
        if self.snapshot_type is None:
            raise NotImplementedError(
                f"{type(self).__name__} must set a class-level `snapshot_type` "
                f"(a frozen dataclass) before snapshot() can be used."
            )
        return self.snapshot_type(
            **{field.name: getattr(self, field.name) for field in dataclasses.fields(self.snapshot_type)}
        )

class CustomAttributeModel(ABC):
    """Marker base for every simulated custom attribute's Python mirror
    (FactoryCoordinate, and any future custom attribute type in any
    domain, e.g. a SensorReading). Purely a discovery hook for
    scan_for_subclasses (see PartInstantiation.evaluate()/
    FischertechnikBridge.instantiate()) -- unlike PartSimulationModel/
    ActionSimulationModel, it declares no shared behavior or constructor,
    since a custom attribute is a plain data holder whose shape is
    entirely up to its own SysML AttributeDefinition and matching
    __init__.
    """
    pass

class Print(ActionSimulationModel):

    def __init__(self, msg):
        self.msg = msg

    def evaluate(self):
        print(self.msg)

