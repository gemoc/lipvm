from typing import Tuple, Optional

from languages.sysmlv2.simulation_models.step_pacer import StepPacer
from languages.sysmlv2.simulation_models.fischertechnik.token import Token
from languages.sysmlv2.simulation_models.generic import CustomAttributeModel, PartSimulationModel, BaseSimulationModel
from languages.sysmlv2.simulation_models.registry import scan_for_subclasses

# One visible hop every this many Factory.tick() calls -- 0.5s at the
# render loop's default 60fps (FactoryVisualization.run()'s tick_rate).
TICKS_PER_STEP = 5

# Range for the live speed slider (factory_visualization.py) -- 1 is the
# fastest this can ever go (a paced step every single Factory.tick()
# call, the render loop's own per-frame ceiling); 90 is 3x slower than
# the TICKS_PER_STEP default above, chosen as "clearly sluggish" without
# being effectively frozen.
TICKS_PER_STEP_MIN = 1
TICKS_PER_STEP_MAX = 90


class Factory(BaseSimulationModel):
    """Central registry of every machine and Token in the simulation, and
    which machine currently owns each Token. Owns this bookkeeping itself,
    rather than each machine holding its own token list, so machine classes
    (ConveyorBeltMachine, a future Gripper, ...) stay pure structural
    mirrors of their SysML PartDefinition, with no token-handling state of
    their own.

    Fischertechnik's own concrete SimulationModel (generic.py) --
    `register_machine`/`get_machine`/`machines`/`spawn_token`/
    `transfer_token`/`owner_of`/`tokens_on`/`tokens` below are all
    Fischertechnik-specific extras beyond that shared contract, used only
    by this domain's own visualization (factory_visualization.py), not
    part of what a different domain needs to provide.
    """

    def __init__(self):
        self._machines = {}
        self._owners = {}
        self._pacer = StepPacer(TICKS_PER_STEP)
        self._events: list[Tuple[str, Optional[str]]] = []

    def register_machine(self, machine):
        if machine.name is None:
            raise ValueError("machine.name must be set before registering it -- Factory keys its registry by name")
        self._machines[machine.name] = machine

    def get_machine(self, name):
        return self._machines.get(name)

    @property
    def machines(self):
        return list(self._machines.values())

    def spawn_token(self, token: Token, machine):
        self._owners[token] = machine

    def transfer_token(self, token: Token, machine):
        self._owners[token] = machine

    def owner_of(self, token: Token):
        return self._owners.get(token)

    def remove_token(self, token: Token) -> None:
        """Deletes a token from the world entirely -- e.g.
        TokenDepoMachine.storeToken() absorbing one into its internal
        tokenCount, where it's no longer a physical entity anyone should
        still see or query. Unlike transfer_token (which only ever
        changes who owns a token, never dropping it from self._owners),
        this is the one place a token actually stops existing.
        """
        self._owners.pop(token, None)

    def tokens_on(self, machine):
        return [token for token, owner in self._owners.items() if owner is machine]

    def machine_at(self, position):
        """The first registered machine whose `contains_position(position)`
        says yes, or `None` if no machine claims that spot. Polymorphic --
        doesn't know or care which machine kinds actually have a
        footprint (PartSimulationModel.contains_position() defaults to
        False; ConveyorBeltMachine is the only current override) -- used
        by a machine that needs to hand a token off to whatever
        physically occupies a position it's dropping it at (e.g.
        VacuumGripperMachine.release()), without that caller needing to
        know about any other machine kind directly.
        """
        return next((machine for machine in self._machines.values() if machine.contains_position(position)), None)

    @property
    def tokens(self):
        return list(self._owners.keys())

    @property
    def ticks_per_step(self) -> int:
        """Live pacing period, shared by every machine (`tick()` below) --
        backed by `self._pacer.period` (`StepPacer`), not a separate copy.
        Exposed here rather than making callers reach into `self._pacer`
        directly, since `_pacer` is otherwise an implementation detail of
        how `tick()` paces itself.
        """
        return self._pacer.period

    @ticks_per_step.setter
    def ticks_per_step(self, value: int) -> None:
        self._pacer.period = max(TICKS_PER_STEP_MIN, min(TICKS_PER_STEP_MAX, int(value)))

    def tick(self):
        """Advances every machine with an active command by one step,
        paced to once every TICKS_PER_STEP calls per machine. Meant to be
        called once per simulation tick (e.g. once per rendered frame) --
        stays framework-agnostic itself, with no pygame/timing dependency,
        so any caller (render loop, test) can drive it. Knows nothing
        about what a "command" means for any particular machine kind --
        that's entirely delegated to machine.advance().
        """
        for machine in self._machines.values():
            if machine.is_idle() or not self._pacer.is_due(machine):
                continue
            machine.tick()
            if machine.is_idle():
                self._pacer.reset(machine)

    def instantiate_machine(self, qualified_name: str, part_def_name: str, attrs: dict) -> None:
        """The actual construction/registration logic behind an
        `InstantiateCommand` (facade_proxy.py) -- idempotent, same
        contract `FischertechnikBridge.instantiate()` used to implement
        directly before it became fire-and-forget: does nothing if
        `qualified_name` is already registered, otherwise resolves
        `part_def_name` against the `PartSimulationModel` registry,
        constructs it, sets any custom-attribute redefinitions from
        `attrs` (attr_name -> (custom_class_name, values) pairs, resolved
        against the `CustomAttributeModel` registry), and registers it.

        No return value: nothing needs the constructed instance back --
        confirmed by checking `PartInstantiation.evaluate()`'s only call
        site (`syntax.py:936`), which discards its return value already.
        Deliberately doesn't import anything from facade_proxy.py --
        draining the queue and deciding when to call this is the caller's
        concern (see main_lipvm_dtsimulation.py's `on_tick`), not
        Factory's, same "framework-agnostic" boundary as `execute_action()`
        below.
        """
        if self.get_machine(qualified_name) is not None:
            return

        klass = scan_for_subclasses(PartSimulationModel)[part_def_name]
        instance = klass(self)
        instance.name = qualified_name

        custom_attribute_registry = scan_for_subclasses(CustomAttributeModel)
        for attr_name, (custom_class_name, values) in attrs.items():
            setattr(instance, attr_name, custom_attribute_registry[custom_class_name](**values))

        self.register_machine(instance)
        print(f"Machine {part_def_name} with name {qualified_name} is Instantiated")

    def execute_action(self, qualified_name: str, action_name: str, args: dict) -> None:
        """Looks up the machine and calls the named action on it with
        `args` -- the actual execution behind an `ActionCommand`
        (facade_proxy.py), which this method deliberately doesn't import
        or know about, same "framework-agnostic" boundary `tick()` and
        `build_snapshot()` already draw for themselves: draining the queue
        and deciding when to call this is the caller's concern (see
        main_lipvm_dtsimulation.py's `on_tick`), not Factory's.
        """
        getattr(self.get_machine(qualified_name), action_name)(**args)

    def record_event(self, item_name: str, source_qualified_name: str = None) -> None:
        """Called by a machine at the exact point it knows an event should
        be reported back to the interpreter (e.g. a command finished, or
        was stopped) -- appends to a plain list, not a queue: unlike the
        interpreter-facing ThreadChannel queues, both this and
        drain_events() only ever run on the pygame thread (inside
        tick()/on_tick()), so there's no cross-thread concern here.

        item_name is the ItemDef's bare declared name (e.g.
        "CBCommandSuccessEventMessage"), never a qualified one -- Factory
        has no access to the parsed SysML model to resolve one itself (see
        instantiate_machine()'s identical bare-name convention on the
        reverse direction). source_qualified_name is this machine's own
        qualified name for a targeted event, or None for a broadcast event
        with no specific origin.
        """
        self._events.append((item_name, source_qualified_name))

    def drain_events(self) -> list[Tuple[str, Optional[str]]]:
        """Returns every event recorded since the last drain, and clears
        the list -- same return-and-clear shape as any other queue-like
        drain in this codebase. Deliberately doesn't import anything from
        facade_proxy.py or resolve item_name to a qualified name itself --
        same framework-agnostic boundary tick()/execute_action()/
        build_snapshot() already draw for themselves; doing that
        resolution and crossing into the interpreter-facing channel is the
        caller's concern (see main_lipvm_dtsimulation.py's `on_tick`).
        """
        events, self._events = self._events, []
        return events

    def build_snapshot(self) -> dict:
        """Pure query: one immutable snapshot of every registered machine's
        current state, keyed by machine name -- see each
        PartSimulationModel's own `snapshot()` (generic.py). Doesn't
        publish it anywhere or know anything about threads/queues/pygame,
        same "framework-agnostic" boundary `tick()` already draws for
        itself above -- publishing this where another thread can safely
        read it (see facade_proxy.py's `SimulationSnapshot`) is the caller's
        concern, not Factory's.
        """
        return {machine.name: machine.snapshot() for machine in self._machines.values()}
