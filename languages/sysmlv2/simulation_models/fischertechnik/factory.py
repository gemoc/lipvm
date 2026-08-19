from languages.sysmlv2.simulation_models.fischertechnik.step_pacer import StepPacer
from languages.sysmlv2.simulation_models.fischertechnik.token import Token
from languages.sysmlv2.simulation_models.generic import CustomAttributeModel, PartSimulationModel
from languages.sysmlv2.simulation_models.registry import scan_for_subclasses

# One visible hop every this many Factory.tick() calls -- 0.5s at the
# render loop's default 60fps (draw_factory's tick_rate).
TICKS_PER_STEP = 30


class Factory:
    """Central registry of every machine and Token in the simulation, and
    which machine currently owns each Token. Owns this bookkeeping itself,
    rather than each machine holding its own token list, so machine classes
    (ConveyorBeltMachine, a future Gripper, ...) stay pure structural
    mirrors of their SysML PartDefinition, with no token-handling state of
    their own.
    """

    def __init__(self):
        self._machines = {}
        self._owners = {}
        self._pacer = StepPacer(TICKS_PER_STEP)

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

    def tokens_on(self, machine):
        return [token for token, owner in self._owners.items() if owner is machine]

    @property
    def tokens(self):
        return list(self._owners.keys())

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
            if machine.currentCommand is None or not self._pacer.is_due(machine):
                continue
            machine.advance()
            if machine.currentCommand is None:
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
        concern (see main_fischertechnik_factory.py's `on_tick`), not
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

    def execute_action(self, qualified_name: str, action_name: str, args: dict) -> None:
        """Looks up the machine and calls the named action on it with
        `args` -- the actual execution behind an `ActionCommand`
        (facade_proxy.py), which this method deliberately doesn't import
        or know about, same "framework-agnostic" boundary `tick()` and
        `build_snapshot()` already draw for themselves: draining the queue
        and deciding when to call this is the caller's concern (see
        main_fischertechnik_factory.py's `on_tick`), not Factory's.
        """
        getattr(self.get_machine(qualified_name), action_name)(**args)

    def build_snapshot(self) -> dict:
        """Pure query: one immutable snapshot of every registered machine's
        current state, keyed by machine name -- see each
        PartSimulationModel's own `snapshot()` (generic.py). Doesn't
        publish it anywhere or know anything about threads/queues/pygame,
        same "framework-agnostic" boundary `tick()` already draws for
        itself above -- publishing this where another thread can safely
        read it (see facade_proxy.py's `LatestSnapshot`) is the caller's
        concern, not Factory's.
        """
        return {machine.name: machine.snapshot() for machine in self._machines.values()}
