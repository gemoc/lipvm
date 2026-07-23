from languages.sysmlv2.simulation_models.fischertechnik.step_pacer import StepPacer
from languages.sysmlv2.simulation_models.fischertechnik.token import Token

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
        self._machines = []
        self._owners = {}
        self._pacer = StepPacer(TICKS_PER_STEP)

    def register_machine(self, machine):
        self._machines.append(machine)

    @property
    def machines(self):
        return list(self._machines)

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
        for machine in self._machines:
            if machine.currentCommand is None or not self._pacer.is_due(machine):
                continue
            machine.advance()
            if machine.currentCommand is None:
                self._pacer.reset(machine)
