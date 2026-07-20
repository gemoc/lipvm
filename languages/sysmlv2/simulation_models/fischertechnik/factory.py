from languages.sysmlv2.simulation_models.fischertechnik.token import Token


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
