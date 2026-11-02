import dataclasses
from abc import ABC, abstractmethod
from typing import Callable, Tuple, Optional


class BaseSimulationModel(ABC):
    """Shared base for a whole simulation domain, which should be extended by
    any SysML parts (or machines) that want to be simulated.
    """

    @abstractmethod
    def instantiate_part(self, qualified_name: str, part_def_name: str, attrs: dict) -> None:
        """Constructs and registers a new part -- idempotent, a no-op if
        `qualified_name` is already registered.

        :param qualified_name: the part's full SysML name
        :param part_def_name: which PartDef to construct
        :param attrs: attr_name -> (custom_class_name, values) pairs, one per custom attribute redefinition
        :return: None
        """
        raise NotImplementedError("Sub-class must implement this method.")

    @abstractmethod
    def set_attribute(self, qualified_name: str, attrs: dict) -> None:
        """Gives an already-instantiated part new configured attribute
        values, from a live update (one entry of a `ModelUpdateCommand`
        batch, see facade_proxy.py); takes effect from the next tick.

        :param qualified_name: the part's full SysML name
        :param attrs: attr_name -> (custom_class_name, values) pairs, same shape as instantiate_machine's
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
    def drain_events(self) -> list[Tuple[str, Optional[str]]]:
        """
        Move all the events emitted by the machine during simulation. These events are moved to another
        entity (e.g., ThreadChannel) to be processed.
        :return:
        """
        raise NotImplementedError("Sub-class must implement this method.")

    @abstractmethod
    def tick(self) -> None:
        """Advances the simulation by one tick.

        :return: None
        """
        raise NotImplementedError("Sub-class must implement this method.")

@dataclasses.dataclass(frozen=True)
class LiveUpdateState:
    """What a visualization shows for live updates (the "update button"),
    provided by the driver each frame through `run()`'s `live_update`: the
    button's label, whether it can be clicked, and lines to show under it
    (e.g. that an update waits for tranquility, or why a file was rejected).
    The visualization only draws it; the driver decides everything.
    """
    label: str
    enabled: bool
    messages: tuple[str, ...] = ()


class SimulationVisualization(ABC):
    """Shared base for a domain's own rendering of its `BaseSimulationModel`
    -- `run()` is the only method called from outside the concrete
    visualization; everything else (drawing, click handling) stays
    private to that implementation.

    `live_update`/`on_submit_update` (optional, both or neither): a function
    returning the current LiveUpdateState, asked every frame, and the
    function to call when its button is clicked while enabled. Without
    them, no live-update controls are shown.
    """

    @abstractmethod
    def run(self, model: BaseSimulationModel, on_start=lambda: None,
            on_tick=lambda: None, tick_rate: int = 60,
            live_update: Optional[Callable[[], LiveUpdateState]] = None,
            on_submit_update: Optional[Callable[[], None]] = None) -> None:
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

    @abstractmethod
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
