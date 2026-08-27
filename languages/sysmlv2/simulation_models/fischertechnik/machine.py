from abc import ABC, abstractmethod
from typing import Optional

from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.generic import PartSimulationModel


class FischertechnikMachine(PartSimulationModel, ABC):
    """Shared base for every Fischertechnik machine (ConveyorBeltMachine,
    VacuumGripperMachine, TokenDepoMachine, TokenProducerMachine, ...) --
    the layer between PartSimulationModel (kept fully domain-agnostic, so
    a future non-Fischertechnik simulation, e.g. water_power_plant,
    doesn't inherit anything Token/Factory-shaped) and this domain's own
    concrete parts (fischertechnik_parts/*.py).

    is_idle()/contains_position() used to live on PartSimulationModel
    itself, but both are inherently Fischertechnik-shaped (is_idle() only
    means anything to Factory.tick()'s own command-dispatch loop;
    contains_position() is about a Token landing in the Factory's
    coordinate space) -- moved down here so a future non-Fischertechnik
    domain doesn't inherit either concept unasked.
    """

    def __init__(self, factory: Factory):
        super().__init__()
        self._factory = factory
        self._sensor_state: dict[str, bool] = {}

    @abstractmethod
    def is_idle(self) -> bool:
        """Whether this machine has no active command to advance --
        Factory.tick() uses this to skip dispatching idle machines, so
        each machine kind's own idle sentinel (None, a dedicated command
        enum member, ...) stays its own business without Factory needing
        to import any machine-kind-specific enum to check it. Left
        abstract (no shared concrete default) rather than e.g.
        `currentCommand is None`, since currentCommand's own type differs
        per machine kind, and at least one machine kind (TokenDepoMachine)
        doesn't tie idleness to currentCommand at all.
        """
        raise NotImplementedError("Subclass need to implement this")

    def emit_event_to_factory(self, event) -> None:
        """Reports `event` back to the Factory, sourced from this
        machine's own name -- the exact one-line body every machine kind
        currently repeats verbatim (e.g. ConveyorBeltMachine's own copy,
        fischertechnik_parts/conveyor_belt.py). `event` is untyped here
        since each machine kind defines its own Enum of possible events
        (CBEventMessages, TokenDepoMessages, ...) with no shared base
        type to name.
        """
        self._factory.record_event(event.value, self.name)

    def contains_position(self, position) -> bool:
        """Whether `position` falls within this machine's own ownable
        footprint -- e.g. a ConveyorBeltMachine claims tokens landing
        anywhere along its own physical extent. Default: no footprint --
        most machine kinds don't passively own space (e.g.
        VacuumGripperMachine only ever gains a token through its own
        explicit grip() action, never by something merely being nearby),
        so this only needs overriding by a machine kind that does.
        """
        return False

    def _sensor_edge(self, name: str, value: bool) -> Optional[bool]:
        """Detects a rising/falling edge on a named boolean sensor,
        comparing `value` against whatever this same `name` reported on
        this machine's own previous call -- True on a rising
        (False->True) edge, False on a falling (True->False) edge, None
        if unchanged. A `name` never seen before is treated as having
        last read False (not "unknown, suppress") -- so a sensor that's
        already true the very first time it's checked still reports a
        rising edge, the same way TokenDepoMachine's own
        `_was_receiver_busy: bool = False` did before this existed.

        This is what a real machine's own sensor read actually is: one
        boolean, compared against its last scan, with "last scan" held
        in a physical register -- not a simulation convenience layered
        on top (see the pub-sub design this replaced, reverted for
        exactly that reason: real fischertechnik hardware has no
        "ownership transferred" event, only sensor value changes).
        `name` lets one machine track more than one independent sensor
        without each needing its own bespoke `_was_x_busy`-shaped
        attribute.
        """
        previous = self._sensor_state.get(name, False)
        self._sensor_state[name] = value
        if value and not previous:
            return True
        if previous and not value:
            return False
        return None
