import dataclasses
from abc import ABC, abstractmethod

class BaseSimulationModel(ABC):
    """Shared base for a whole simulation domain (Fischertechnik's
    `Factory`, and any future domain, e.g. water_power_plant) -- the
    top-level object whoever drives the simulation constructs and drives.
    """

    @abstractmethod
    def instantiate_machine(self, qualified_name: str, part_def_name: str, attrs: dict) -> None:
        """Constructs and registers a new part -- idempotent, a no-op if
        `qualified_name` is already registered.

        :param qualified_name: the part's full SysML name
        :param part_def_name: which PartDef to construct
        :param attrs: attr_name -> (custom_class_name, values) pairs, one per custom attribute redefinition
        :return: None
        """
        raise NotImplementedError("Sub-class must implement this method.")

    @abstractmethod
    def execute_action(self, qualified_name: str, action_name: str, args: dict) -> None:
        """Calls a named action on an already-instantiated part.

        :param qualified_name: the target part's full SysML name
        :param action_name: which method to call on it
        :param args: keyword arguments for that call
        :return: None
        """
        raise NotImplementedError("Sub-class must implement this method.")

    @abstractmethod
    def build_snapshot(self) -> dict:
        """Builds an immutable snapshot of every registered part's current
        state, keyed by qualified name -- safe for another thread to read.

        :return: dict of qualified_name -> that part's snapshot
        """
        raise NotImplementedError("Sub-class must implement this method.")

    @abstractmethod
    def tick(self) -> None:
        """Advances the simulation by one tick.

        :return: None
        """
        raise NotImplementedError("Sub-class must implement this method.")

class SimulationVisualization(ABC):
    """Shared base for a domain's own rendering of its `BaseSimulationModel`
    -- `run()` is the only method called from outside the concrete
    visualization; everything else (drawing, click handling) stays
    private to that implementation.

    No shared/default implementation -- Fischertechnik's is the only
    visualization that exists today (and it's pygame-specific), so
    there's nothing yet known to be common across domains.
    """

    @abstractmethod
    def run(self, model: BaseSimulationModel, on_start=lambda: None,
            on_tick=lambda: None, tick_rate: int = 60) -> None:
        raise NotImplementedError("Sub-class must implement this method.")

class ActionSimulationModel(ABC):

    @abstractmethod
    def evaluate(self):
        raise NotImplementedError("Sub-class must implement this method.")

class PartSimulationModel(ABC):
    """Shared base for every simulated part (ConveyorBeltMachine, and any
    future machine kind). Carries a `name` -- a plain opaque identifier
    the caller assigns (e.g. a SysML qualified name); Factory keys its
    machine registry by it, so it must be unique.

    `snapshot()` builds `snapshot_type` (a subclass-set frozen dataclass)
    by reflecting over its declared fields and pulling each one off
    `self` -- so a subclass lists its attributes once, not twice.
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
        """Reflects over `snapshot_type`'s declared fields and pulls each
        one off `self` via `getattr`. A field with no matching attribute
        fails loudly (`AttributeError`) rather than silently producing a
        wrong snapshot.
        """
        if self.snapshot_type is None:
            raise NotImplementedError(
                f"{type(self).__name__} must set a class-level `snapshot_type` "
                f"(a frozen dataclass) before snapshot() can be used."
            )
        return self.snapshot_type(
            **{field.name: getattr(self, field.name) for field in dataclasses.fields(self.snapshot_type)}
        )

    def tick(self) -> None:
        """This method will be called by the simulation for every tick."""
        raise NotImplementedError("Sub-class must implement this method.")

class CustomAttributeModel(ABC):
    """Marker base for every simulated custom attribute's Python mirror
    (FactoryCoordinate, and any future custom attribute type). Purely a
    discovery hook for `scan_for_subclasses()` -- no shared behavior,
    since a custom attribute's shape is entirely up to its own SysML
    AttributeDefinition.
    """
    pass

class Print(ActionSimulationModel):

    def __init__(self, msg):
        self.msg = msg

    def evaluate(self):
        print(self.msg)
