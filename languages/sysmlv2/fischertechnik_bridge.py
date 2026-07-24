from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.generic import CustomAttributeModel, PartSimulationModel
from languages.sysmlv2.simulation_models.registry import scan_for_subclasses


class FischertechnikBridge:
    """The only thing allowed to touch Factory/ConveyorBeltMachine/the
    PartSimulationModel registry directly. Everything on the interpreter
    side (PartInstantiation.evaluate()) goes through this narrow surface
    instead of reaching into the simulation directly, so a later swap to
    queue-based messaging (see OVERVIEW-TASKS.md task 5) only has to change
    what's inside these methods, not every call site that needed a
    simulation object.

    Fischertechnik-specific on purpose, not a generic simulation bridge --
    see OVERVIEW-TASKS.md/URGENT-STEP1-SUBTASKS.md for why a second
    simulation domain (e.g. water_power_plant) would get its own bridge
    class, built against its actual shape once it exists, rather than
    forcing every domain through one speculative shared interface now.
    """

    def __init__(self, factory: Factory):
        self._factory = factory

    def instantiate(self, qualified_name: str, part_def_name: str, **attrs):
        """Idempotent: returns the existing instance registered under
        `qualified_name` if there is one (Factory is the single source of
        truth for this, not a separate cache here), otherwise creates a
        live PartSimulationModel instance for `part_def_name` (e.g.
        "ConveyorBeltMachine"), names it `qualified_name`, registers it
        with the Factory, and returns it. Each entry in `attrs` is a plain
        (class_name, values) pair (not a SysML AST node), one per
        CompositeCustomValue redefinition on the usage (built by
        PartInstantiation.evaluate(), e.g. "placementCoordinate" ->
        ("FactoryCoordinate", {"x": 10.0, "y": 0.0, "degrees": 0.0})) --
        attr_name is set on the instance to class_name(**values), resolved
        against the same kind of registry as part_def_name, so a second
        custom attribute (beyond FactoryCoordinate) needs no changes here.
        """
        existing = self._factory.get_machine(qualified_name)
        if existing is not None:
            return existing

        klass = scan_for_subclasses(PartSimulationModel)[part_def_name]
        instance = klass(self._factory)
        instance.name = qualified_name

        custom_attribute_registry = scan_for_subclasses(CustomAttributeModel)
        for attr_name, (custom_class_name, values) in attrs.items():
            setattr(instance, attr_name, custom_attribute_registry[custom_class_name](**values))

        self._factory.register_machine(instance)
        return instance

    def get_value_from_instance_attribute(self, qualified_name: str, attribute_name: str):
        return getattr(self._factory.get_machine(qualified_name), attribute_name)

    def call_action(self, qualified_name: str, action_name: str, **args):
        getattr(self._factory.get_machine(qualified_name), action_name)(**args)
