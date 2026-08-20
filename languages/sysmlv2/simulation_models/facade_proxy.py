"""Generic (domain-agnostic) Facade+Proxy infrastructure for thread-confined
access to a simulation object owned by the simulation visualization thread.
"""

import queue
from dataclasses import dataclass

from core.language import RuntimeStateElement


class PartNotReadyError(Exception):
    """Raised when a part isn't in the published snapshot yet -- either no
    snapshot has been published, or this part specifically hasn't been
    instantiated yet. An ordinary startup race, not a real error -- its
    own exception type so a caller that wants to treat "not ready yet" as
    non-fatal (e.g. a transition guard) can catch exactly this.
    """


@dataclass(frozen=True)
class InstantiateCommand:
    """Fire-and-forget style command that is executed by the SysML interpreter when
    a part needs to be instantiated.

    qualified_name: the part's full SysML name
    part_def_name: which PartDef to construct
    attrs: attr_name -> (custom_class_name, values) pairs, one per
        CompositeCustomValue redefinition (e.g. "placementCoordinate" ->
        ("FactoryCoordinate", {"x": 10.0, "y": 0.0, "degrees": 0.0}))
    """
    qualified_name: str
    part_def_name: str
    attrs: dict


@dataclass(frozen=True)
class ActionCommand:
    """Fire-and-forget style command that is executed by the SysML interpreter when
    an needs to be performed, which will affect the simulation state.

    qualified_name: the target part's full SysML name
    action_name: which method to call on it
    args: keyword arguments for that call
    """
    qualified_name: str
    action_name: str
    args: dict


class SimulationSnapshot:
    """Single-value "topic" one thread publishes to and any number of
    others read from -- always holds just the latest value, no backlog (a
    `queue.Queue` would be the wrong tool: a stale snapshot is worthless
    once a newer one exists).

    `publish()` is a single reference assignment, atomic under CPython's
    GIL, so no lock is needed on either side. `read()` returns `None`
    before the first `publish()` call -- callers must handle that.
    """

    def __init__(self):
        self._value = None

    def publish(self, value) -> None:
        self._value = value

    def read(self):
        return self._value


class ThreadChannel(RuntimeStateElement):
    """Bundles everything the interpreter thread and the owning thread use
    to communicate: a published snapshot for reads, plus one-way queues
    for `instantiate`/`call_action` -- all 3 `SimulationBridge` operations,
    none of them blocking.

    A `RuntimeStateElement` so it can be registered directly on `runtime`
    and reached as `runtime.channel` -- `SimulationBridge` itself holds no
    state and is never instantiated, just a namespace of static methods
    that take this channel as an explicit argument.

    self.latest_snapshot: the latest SimulationSnapshot published by the Simulation Model and its visualization
    self.action_queue: a queue of actions to be executed by the Simulation model and its visualization
    self.instantiate_queue: a queue of parts to be instantiated in the Simulation model and its visualization
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.latest_snapshot = SimulationSnapshot()
        self.action_queue = queue.Queue()
        self.instantiate_queue = queue.Queue()

class SimulationBridge:
    """Static utility surface for whatever simulation domain is plugged in
    underneath -- everything on the interpreter side goes through this
    instead of reaching into a domain's own simulation model directly.

    Never instantiated: every method takes the `ThreadChannel` it operates
    on as an explicit argument (reached as `runtime.channel`) rather than
    holding one as instance state. Domain-agnostic: only deals in
    `qualified_name` strings, plain dicts, and the generic command/channel
    types above -- nothing here knows about any specific domain's shape.

    No `get_snapshot()`/`channel` wrapper here -- a caller with a
    `ThreadChannel` just reads `channel.latest_snapshot.read()` directly.
    """

    @staticmethod
    def instantiate(channel: ThreadChannel, qualified_name: str, part_def_name: str, **attrs):
        """Enqueues an `InstantiateCommand` -- fire-and-forget. The owning
        thread drains and executes these once per tick.
        """
        channel.instantiate_queue.put(InstantiateCommand(qualified_name, part_def_name, attrs))

    @staticmethod
    def call_action(channel: ThreadChannel, qualified_name: str, action_name: str, **args):
        """Enqueues an `ActionCommand` -- fire-and-forget. The owning
        thread drains and executes these once per tick; it's the only
        thread that ever calls a method on a machine.
        """
        channel.action_queue.put(ActionCommand(qualified_name, action_name, args))

    @staticmethod
    def read_attribute_from_snapshot(snapshot, qualified_name: str, attribute_name: str):
        """Resolves one attribute off an already-captured snapshot (the
        dict from a single `channel.latest_snapshot.read()` call). Callers
        must capture that value once per evaluation pass and reuse it for
        every lookup in that pass -- reading fresh per lookup can tear
        reads across a compound guard.

        Raises `PartNotReadyError` if no snapshot has been published yet,
        or if `qualified_name` isn't in it -- an ordinary startup race,
        not a real failure. Any other missing attribute surfaces as a
        normal `AttributeError`.
        """
        if snapshot is None or qualified_name not in snapshot:
            raise PartNotReadyError(
                f"{qualified_name!r} not in the latest published snapshot yet -- "
                f"can't read {attribute_name!r} on it (owning thread hasn't drained "
                f"its instantiate() request yet)."
            )
        return getattr(snapshot[qualified_name], attribute_name)
