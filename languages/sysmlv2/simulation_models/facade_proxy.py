"""Generic (domain-agnostic) Facade+Proxy infrastructure for thread-confined
access to a simulation object owned by another thread -- see
TODAYS-TASKS.md for the roadmap this implements and HOMEWORK-SAYYID.md
task 1 for the race condition it exists to close.

Nothing in this file knows about Factory, ConveyorBeltMachine, or any
Fischertechnik vocabulary. Every domain-specific bridge (FischertechnikBridge
today, and any future one, e.g. for a water_power_plant domain) implements
`SimulationBridge`'s 3 methods, so the interpreter-facing call sites in
runtime.py (AttributeReference.evaluate()/ActualAction.evaluate()/
PartInstantiation.evaluate()) never change shape regardless of domain.

All 3 operations turned out to be non-blocking once their actual call sites
were checked, not just 2 of 3 as originally planned (see TODAYS-TASKS.md):
- reads publish/read a `SimulationSnapshot`, once per tick, no request at all.
- `call_action`/`instantiate` are both fire-and-forget one-way queues
  (`ActionCommand`/`InstantiateCommand`) -- confirmed by checking their real
  call sites discard the return value (runtime.py:445's call site and
  syntax.py:936 respectively), not just the method signatures themselves.

So there's currently no shared request/response machinery in this file --
none of the 3 operations need one. If a future operation genuinely needs a
reply, that's the case this file doesn't have a mechanism for yet; add it
then; see `SimulationBridge`'s docstring.
"""

import queue
from dataclasses import dataclass

from core.language import RuntimeStateElement


class PartNotReadyError(Exception):
    """Raised by `SimulationBridge.read_attribute_from_snapshot()`
    when the part it's asked about doesn't exist in the published snapshot
    yet -- either because no snapshot has been published at all, or
    because this specific `qualified_name` isn't in the one that has been.
    Both are the same situation from a caller's point of view: the
    interpreter asked for a part to be instantiated (fire-and-forget,
    `instantiate()`) and the owning thread just hasn't drained/published
    that yet -- an ordinary startup race, not a real error.

    Deliberately its own exception type rather than a bare `RuntimeError`,
    so a caller that specifically wants to treat "not ready yet" as
    non-fatal (e.g. `TransitionTrigger.evaluate()`, runtime.py) can catch
    exactly this and nothing else -- see its docstring for why "not ready"
    should mean "this trigger doesn't fire yet," not a crash.
    """


@dataclass(frozen=True)
class InstantiateCommand:
    """Mirrors SimulationBridge.instantiate()'s arguments. `attrs` is a
    plain dict of attr_name -> (custom_class_name, values) pairs, same
    wire format FischertechnikBridge.instantiate() always documented --
    resolving custom_class_name against whatever registry the owning
    thread's executor uses is that executor's job, not this dataclass's.

    Fire-and-forget, like `ActionCommand`: nothing on the interpreter side
    ever used `instantiate()`'s return value at its real call site --
    `PartInstantiation.evaluate()` (runtime.py:894) used to `return` it,
    but its own caller, `syntax.py:936`, discards it (`an_instantiation.evaluate(runtime)`,
    no assignment). No matching response type needed.
    """
    qualified_name: str
    part_def_name: str
    attrs: dict


@dataclass(frozen=True)
class ActionCommand:
    """Mirrors SimulationBridge.call_action()'s arguments -- fire-and-forget:
    nothing on the interpreter side ever used call_action()'s return value
    (confirmed by reading ActualAction.evaluate()'s call site, runtime.py:445).
    The owning thread drains these from `ThreadChannel.action_queue` and
    executes them (e.g. via Factory.execute_action()) once per tick, no
    reply pushed anywhere.
    """
    qualified_name: str
    action_name: str
    args: dict


class SimulationSnapshot:
    """Generic 'topic' a single owning thread publishes to and any number
    of other threads read from -- holds whatever was last published;
    readers always see the newest value, never a backlog, and there is no
    queue to drain (a `queue.Queue` is the wrong tool here: it hands off
    items one at a time and preserves history, but a stale snapshot is
    worthless the instant a newer one exists -- this holds exactly one
    value, always the latest).

    `publish()` is a single reference assignment, atomic under CPython's
    GIL -- a concurrent `read()` always sees either the fully-old or the
    fully-new value, never something in between, so no lock is needed on
    either side. Domain-agnostic on purpose, same reasoning as
    `SimulationBridge`: knows nothing about Factory or any particular
    snapshot shape, only that *some* immutable value gets published and
    read.

    `read()` returns `None` before the first `publish()` call (e.g. before
    "Start" is clicked and the owning thread's first tick has run) --
    callers need to handle that explicitly.
    """

    def __init__(self):
        self._value = None

    def publish(self, value) -> None:
        self._value = value

    def read(self):
        return self._value


class ThreadChannel:
    """Bundles every channel the interpreter thread and the owning
    (simulation) thread use to communicate: a published snapshot for
    reads, and one-way command queues for `instantiate`/`call_action` --
    all 3 `SimulationBridge` operations, none of them blocking.

    Deliberately a plain class, not a dataclass: this is a long-lived
    registry/handle constructed once and held by reference from both
    threads for the whole program run, not a value object meaningfully
    compared by its contents -- same reasoning `Factory` (also a container
    of other stateful things) is a plain class rather than a dataclass.

    Constructs its own `SimulationSnapshot`/`Queue`s internally -- a caller
    just does `ThreadChannel()` and gets a ready-made bundle, rather than
    assembling the pieces itself.
    """

    def __init__(self):
        self.latest_snapshot = SimulationSnapshot()
        self.action_queue = queue.Queue()
        self.instantiate_queue = queue.Queue()

class SimulationBridge(RuntimeStateElement):
    """The interpreter-facing surface for whatever simulation domain is
    plugged in underneath -- everything on the interpreter side
    (PartInstantiation.evaluate()/AttributeReference.evaluate()/
    ActualAction.evaluate() in runtime.py) goes through this narrow
    surface instead of reaching into a domain's own simulation model
    (e.g. Fischertechnik's `Factory`) directly.

    Already domain-agnostic, not just intended to be: every operation
    below deals only in `qualified_name` strings, plain dicts, and the
    generic `InstantiateCommand`/`ActionCommand`/`ThreadChannel` types --
    nothing here references `Factory`, `ConveyorBeltMachine`, or any other
    Fischertechnik-specific shape. A second simulation domain (e.g.
    water_power_plant) reuses this class as-is; only its own simulation
    model (the thing actually draining `channel` and executing commands
    each tick -- see `main_lipvm_dtsimulation.py`'s `on_tick`) needs
    to be domain-specific.

    Holds no reference to any domain's simulation model at all -- only
    `channel`, a `ThreadChannel`. Every one of the 3 operations is now
    non-blocking (reads via a published snapshot, `instantiate`/
    `call_action` both fire-and-forget queues -- see TODAYS-TASKS.md), so
    this class never needs to reach a domain's simulation model directly,
    which is what makes the thread-confinement guarantee real rather than
    just documented.
    """

    def __init__(self, channel: ThreadChannel, **kwargs):
        super().__init__(**kwargs)
        self._channel = channel

    def instantiate(self, qualified_name: str, part_def_name: str, **attrs):
        """Enqueues an `InstantiateCommand` instead of constructing/
        registering the machine directly -- fire-and-forget, thread-
        confined-safe, now that nothing consumes this method's return
        value (confirmed: `PartInstantiation.evaluate()`'s only call site,
        `syntax.py:936`, discards it). The owning thread drains and
        executes these once per tick (see
        `Factory.instantiate_machine()`/main_lipvm_dtsimulation.py's
        `on_tick`), same as `call_action()` below. `attrs` is a plain dict
        of attr_name -> (custom_class_name, values) pairs, one per
        CompositeCustomValue redefinition on the usage (built by
        PartInstantiation.evaluate(), e.g. "placementCoordinate" ->
        ("FactoryCoordinate", {"x": 10.0, "y": 0.0, "degrees": 0.0})).
        """
        self._channel.instantiate_queue.put(InstantiateCommand(qualified_name, part_def_name, attrs))

    @staticmethod
    def read_attribute_from_snapshot(snapshot, qualified_name: str, attribute_name: str):
        """Resolves one attribute off an already-captured snapshot value --
        the dict returned by a single `get_snapshot()` call. Callers must
        capture that value once per evaluation pass (see
        `ExecutableStateUsage._find_matching_transition()`, runtime.py) and
        reuse it for every lookup in that pass; calling `get_snapshot()`
        fresh per lookup reopens the torn-read window this exists to close.

        Raises `PartNotReadyError` (not a crash-worthy error -- see its
        docstring) if no snapshot has been published yet, or if
        `qualified_name` isn't in the one that has -- both mean the owning
        thread hasn't caught up to an `instantiate()` call yet, an ordinary
        startup race, not a real failure. Any other missing attribute (a
        typo, a genuinely wrong name) still surfaces as a normal
        `AttributeError` from `getattr`, since that's not the same
        situation.
        """
        if snapshot is None or qualified_name not in snapshot:
            raise PartNotReadyError(
                f"{qualified_name!r} not in the latest published snapshot yet -- "
                f"can't read {attribute_name!r} on it (owning thread hasn't drained "
                f"its instantiate() request yet)."
            )
        return getattr(snapshot[qualified_name], attribute_name)

    def call_action(self, qualified_name: str, action_name: str, **args):
        """Enqueues an `ActionCommand` instead of calling the machine
        directly -- fire-and-forget, thread-confined-safe, matching
        `call_action()`'s contract (nothing ever used its return value,
        see ActionCommand's docstring). The owning thread drains and
        executes these once per tick (see main_lipvm_dtsimulation.py's
        `on_tick`), the only thread ever allowed to actually call a method
        on a machine (see HOMEWORK-SAYYID.md task 1).
        """
        self._channel.action_queue.put(ActionCommand(qualified_name, action_name, args))

    @property
    def channel(self):
        return self._channel

    def get_snapshot(self):
        return self._channel.latest_snapshot.read()