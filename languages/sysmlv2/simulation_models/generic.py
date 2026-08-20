import dataclasses
from abc import ABC, abstractmethod

class BaseSimulationModel(ABC):
    """Shared base for a whole simulation domain (Fischertechnik's
    `Factory`, and any future domain, e.g. water_power_plant) -- the
    top-level object `main_fischertechnik_factory.py` (or its eventual
    generic successor) constructs and drives, as opposed to
    PartSimulationModel below (one machine within that domain).

    Narrow on purpose: only the methods actually called on a domain's
    simulation model from *outside* it -- derived by grepping the real
    call sites (see GENERIC-SIMULATION-TASKS.md), not guessed. Everything
    else a concrete domain needs (Fischertechnik's token/machine
    bookkeeping -- `register_machine`, `spawn_token`, `transfer_token`,
    `owner_of`, `tokens_on`, `tokens`, `get_machine`) stays on that
    domain's own class, not part of this contract -- normal subclassing,
    this only demands the minimum every domain must provide.

    `instantiate_machine`/`execute_action`/`build_snapshot` are what the
    owning thread's `ThreadChannel`-draining logic calls each tick (see
    `main_fischertechnik_factory.py`'s `on_tick`) -- the actual execution
    behind `SimulationBridge`'s fire-and-forget `instantiate()`/
    `call_action()` and its published-snapshot reads. `tick()` is called
    separately, once per rendered frame, by the visualization layer (see
    `factory_visualization.py`) -- not `ThreadChannel`-connected, but
    needed for the same reason: every domain needs some "advance one
    tick" operation, regardless of what channel wiring exists around it.
    """

    @abstractmethod
    def instantiate_machine(self, qualified_name: str, part_def_name: str, attrs: dict) -> None:
        raise NotImplementedError("Sub-class must implement this method.")

    @abstractmethod
    def execute_action(self, qualified_name: str, action_name: str, args: dict) -> None:
        raise NotImplementedError("Sub-class must implement this method.")

    @abstractmethod
    def build_snapshot(self) -> dict:
        raise NotImplementedError("Sub-class must implement this method.")

    @abstractmethod
    def tick(self) -> None:
        raise NotImplementedError("Sub-class must implement this method.")

class SimulationVisualization(ABC):
    """Shared base for a domain's own rendering of its BaseSimulationModel
    -- the single entry point whoever drives the simulation (currently
    `main_fischertechnik_factory.py`, or its eventual generic successor)
    calls, regardless of domain.

    Narrow on purpose, same derivation as `BaseSimulationModel` above: the
    only thing ever called on Fischertechnik's own visualization from
    *outside* `factory_visualization.py` is its `run(model, on_start,
    on_tick, tick_rate)` -- every other method on `FactoryVisualization`
    (drawing individual machines/tokens/panels, mouse click handling) is
    only ever called from *within* that same class, so it stays private to
    that concrete implementation, not part of this contract -- same
    reasoning `Factory`'s own token/machine bookkeeping stays off
    `BaseSimulationModel`.

    `run()` is left purely abstract, no shared/default implementation --
    Fischertechnik's is the only visualization that exists to design
    against (it's pygame-specific; a future domain might not even use
    pygame), so there's nothing yet that's actually known to be common
    across domains to put here.
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

