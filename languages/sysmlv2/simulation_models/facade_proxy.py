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
class SimulationBridgeCommand:

    pass

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


@dataclass(frozen=True)
class EventCommand:
    """Fire-and-forget command flowing the other way: an event the
    simulation side finished producing, to be delivered into the
    interpreter's ExecutableStateUsage mailboxes (see EVENT-QUEUE-DESIGN.md).

    item_name: the ItemDef's bare declared name (e.g.
        "VGRCommandSuccessEventMessage"), not a qualified one -- the
        simulation side has no access to the parsed SysML model to resolve
        one itself, so resolution to a qualified name happens later, on
        the interpreter thread (see LookupTable.get_reference_by_name()).
    source_qualified_name: the emitting part's qualified name (e.g.
        "Main::vgr1"), or None for a broadcast event with no specific origin
        (e.g. StopEventMessage).
    """
    item_name: str
    source_qualified_name: str | None = None


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
    none of them blocking. The one exception is lockstep while an update is
    pending (design doc, Topic 10): the simulation asks on
    `move_request_queue` and waits for the answer on `move_permission_queue`,
    the only place where one thread waits for the other.

    A `RuntimeStateElement` so it can be registered directly on `runtime`
    and reached as `runtime.channel` -- `SimulationBridge` itself holds no
    state and is never instantiated, just a namespace of static methods
    that take this channel as an explicit argument.

    self.latest_snapshot: the latest SimulationSnapshot published by the Simulation Model and its visualization
    self.action_queue: a queue of actions to be executed by the Simulation model and its visualization
    self.instantiate_queue: a queue of parts to be instantiated in the Simulation model and its visualization, at startup (live additions come on model_update_queue)
    self.model_update_queue: a queue of model changes from live updates (one ModelUpdateCommand batch per update: added parts and changed attribute values)
    self.event_queue: a queue of events produced by the Simulation model, to be delivered to the interpreter
    self.move_request_queue: the simulation's "may I move past frame N?", a frame number, while an update is pending
    self.move_permission_queue: the interpreter's "go", the same frame number; both sides raise on a mismatch
    self.lockstep_enabled: whether a simulation takes part in the request and response; False (e.g. in tests)
        means nobody will ask, so the interpreter must not wait. Set by the driver before the interpreter thread starts
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.latest_snapshot = SimulationSnapshot()
        self.action_queue = queue.Queue()
        self.instantiate_queue = queue.Queue()
        self.model_update_queue = queue.Queue()
        self.event_queue = queue.Queue()

        # Live experience-related functionality
        self.move_request_queue = queue.Queue()
        self.move_permission_queue = queue.Queue()
        self.lockstep_enabled = False

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
    def send_model_update(channel: ThreadChannel, command):
        """Enqueues one live update's batch of model changes (a
        `ModelUpdateCommand`, built by the `SynchronizationManager` in
        synchronization.py) -- fire-and-forget. The owning thread drains and
        applies these once per tick, so every change in the batch lands in
        the same frame.
        """
        channel.model_update_queue.put(command)

    @staticmethod
    def emit_event(channel: ThreadChannel, item_name: str, source_qualified_name: str | None = None):
        """Enqueues an `EventCommand` -- fire-and-forget, the reverse
        direction from `instantiate`/`call_action`. The owning thread
        (simulation side) calls this once per tick with whatever it
        collected via `Factory.drain_events()`; the interpreter thread
        drains `channel.event_queue` and delivers each one into every
        running `ExecutableStateUsage`'s `pending` mailbox (see
        EVENT-QUEUE-DESIGN.md).
        """
        channel.event_queue.put(EventCommand(item_name, source_qualified_name))
