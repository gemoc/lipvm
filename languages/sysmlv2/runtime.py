from pyecore.ecore import MetaEClass, EAttribute, EReference, EString, EObject, EProxy, EEnum

from core.language import AbstractSyntaxElement, RuntimeStateElement
from languages.sysmlv2.sysml_utility_classes import qualified_name

# Plain pyecore EEnums, not Python enum.Enum subclasses — EAttribute(eType=...)
# requires an EClassifier (EEnum), which a Python Enum class isn't.
TypeKind = EEnum('TypeKind', literals=['SCALAR', 'PART', 'ITEM', 'ACTION', 'CUSTOM', 'ENUM', 'UNKNOWN'])

ParamDirection = EEnum('ParamDirection', literals=['IN', 'OUT', 'INOUT'])

ScalarType = EEnum('ScalarType', literals=['NONE', 'BOOLEAN', 'INTEGER', 'REAL', 'STRING'])

# Only the scalar names ScalarValues.json actually declares are mapped;
# names outside this set (e.g. Rational, Natural, Complex) still get a
# SCALAR TypeRef, just with scalar_type left unset.
_SCALAR_TYPE_BY_NAME = {
    'Boolean': ScalarType.BOOLEAN,
    'String': ScalarType.STRING,
    'Integer': ScalarType.INTEGER,
    'Real': ScalarType.REAL,
}

class ElementDefinition(RuntimeStateElement, metaclass=MetaEClass):
    """Runtime registry entry for a named SysML Definition.

    Built once when a Namespace is evaluated, so the rest of the AST can
    resolve a Definition by qualified name during execution instead of
    re-walking the model. `definition` points back at the syntax.py AST node
    (e.g. an ActionDefinition) this entry was built from; the structural
    interpretation of that node stays in its own evaluate(), not here.

    Declared name is inherited from RuntimeStateElement.name rather than
    redeclared here; qualified_name stays its own field, since it's derived
    (package-qualified) rather than a plain re-use of the declared name.
    """

    qualified_name = EAttribute(eType=EString, lower=1, upper=1)
    definition = EReference(eType=AbstractSyntaxElement, lower=1, upper=1)

class EnumerationDefinition(ElementDefinition, metaclass=MetaEClass):

    '''
    The enumeration defined in SysML is expected to only containts String literals. Thus this class
    will only stored those literals as a list of contained values
    '''
    contained_values = EAttribute(eType=EString, lower=1, upper=-1)

class PartDef(ElementDefinition, metaclass=MetaEClass):

    pass

class Reference(ElementDefinition, metaclass=MetaEClass):
    reference_type = EAttribute(eType=EString, lower=1, upper=1)

class Value(RuntimeStateElement, metaclass=MetaEClass):
    # An abstract class to specify a value
    pass

class LiteralValue(Value):
    el = EAttribute(eType=EString, lower=1, upper=1)

class ReferenceValue(Value):
    el = EReference(eType=Reference, lower=1, upper=1, containment=False)

class Record(ElementDefinition, metaclass=MetaEClass):
    element_type = EReference(eType=ElementDefinition, lower=1, upper=1, containment=False)

class LookupTable(EObject, metaclass=MetaEClass):
    records = EReference(eType=Record, lower=0, upper=-1, containment=True)

    def get_reference(self, qualified_name):
        for b in self.records:
            if b.qualified_name == qualified_name:
                return b
        return None

    def has_reference(self, qualified_name):
        return self.get_reference(qualified_name) is not None

    def set_reference(self, qualified_name, value):
        reference = self.get_reference(qualified_name)
        if reference is not None:
            reference.element_type = value
        else:
            self.records.append(Record(qualified_name=qualified_name, element_type=value))

class TypeRef(RuntimeStateElement, metaclass=MetaEClass):

    kind =  EAttribute(eType=TypeKind, lower=1, upper=1, containment=False)
    scalar_type =  EAttribute(eType=ScalarType, lower=0, upper=1)
    reference_type = EReference(eType=Reference, lower=0, upper=1)

class Parameter(ElementDefinition, metaclass=MetaEClass):
    """A named parameter slot: either a formal parameter declared on an
    ActionDef/StateDef (e.g. Print's `msg`, `value` unset), or a bound
    argument at a specific PerformActionUsage call site (`value` set to the
    AST literal/expression node it was bound to, `type` pointing back at the
    formal Parameter it fulfills).
    """
    type = EReference(eType=TypeRef, lower=1, upper=1)
    direction = EAttribute(eType=ParamDirection, lower=1, upper=1)
    default_value = EReference(eType=Value, lower=0, upper=1, containment=True)

class Argument(ElementDefinition, metaclass=MetaEClass):
    """A named parameter slot: either a formal parameter declared on an
    ActionDef/StateDef (e.g. Print's `msg`, `value` unset), or a bound
    argument at a specific PerformActionUsage call site (`value` set to the
    AST literal/expression node it was bound to, `type` pointing back at the
    formal Parameter it fulfills).
    """
    value = EReference(eType=Value, lower=0, upper=1, containment=True)

class AttributeUsageElement(ElementDefinition, metaclass=MetaEClass):

    type = EReference(eType=TypeRef, lower=1, upper=1)
    default_value = EReference(eType=Value, lower=0, upper=1, containment=True)

class CustomAttributeDefinition(ElementDefinition, metaclass=MetaEClass):

    contained_attribute_use = EReference(eType=AttributeUsageElement, lower=1, upper=-1, containment=True)

class ActionDef(ElementDefinition, metaclass=MetaEClass):
    """Runtime registry entry for an ActionDefinition."""

    parameters = EReference(eType=Parameter, lower=0, upper=-1, containment=True)

    def add_parameter(self, parameter):
        self.parameters.append(parameter)

class ActualAction(ElementDefinition, metaclass=MetaEClass):
    """A single performance/call occurrence of an ActionDef (e.g. `pEntry`
    performing `Print`), analogous to how ExecutableStateUsage is the
    running occurrence of a StateDef.
    """

    # Which ActionDef this call performs. None if it doesn't resolve.
    action_def = EReference(eType=Reference, lower=0, upper=1, containment=False)

    # The bound call-site arguments (e.g. msg="Entry"), each a Parameter
    # whose `type` points back at the formal Parameter it fulfills.
    arguments = EReference(eType=Argument, lower=0, upper=-1, containment=True)

class ItemDef(ElementDefinition, metaclass=MetaEClass):
    """Runtime registry entry for an ItemDefinition (a message/event type)."""

    # TODO: attributes, once AttributeDefinition/AttributeUsage support lands.
    pass

class TransitionTrigger(RuntimeStateElement, metaclass=MetaEClass):
    """Placeholder for a Transition's trigger condition — what an incoming
    item must match for the Transition to fire. No fields yet; kept as its
    own marker type (rather than reusing ItemDef directly) so richer trigger
    matching (item kind, guard, etc.) can grow independently of the item
    type registry later.
    """
    pass

class TransitionTriggerBySignal(TransitionTrigger, metaclass=MetaEClass):

    signal_origin = EReference(eType=Reference, lower=0, upper=1, containment=False)

class TransitionGuard(RuntimeStateElement, metaclass=MetaEClass):

    pass

class Transition(RuntimeStateElement, metaclass=MetaEClass):
    """A single transition declared by a StateDef, from one of its
    StateUsage substates to another.

    Built once from a TransitionUsage's source/trigger/target/effect. Firing
    it (matching an incoming item against `trigger`, running `effect`,
    moving the owning ExecutableStateUsage's `current` to `target`) is a
    dispatch concern left for later; this only holds the structure needed to
    find and fire one.
    """
    definition = EReference(eType=AbstractSyntaxElement, lower=0, upper=1, containment=False)

    # Reference to the StateUsage substate this transition fires out of
    # (e.g. Idle).
    source = EReference(eType=Reference, lower=0, upper=1, containment=False)

    # None means an unconditional/completion transition (e.g. the one fired
    # right after MySimulationDefinition's entry action finishes).
    trigger = EReference(eType=TransitionTrigger, lower=0, upper=1, containment=False)
    guard = EReference(eType=TransitionGuard, lower=0, upper=1, containment=False)

    # The effect action performed when this transition fires, if any. None
    # means no effect.
    effect = EReference(eType=ActualAction, lower=0, upper=1, containment=False)

    # Reference to the StateUsage substate this transition fires into.
    target = EReference(eType=Reference, lower=1, upper=1, containment=False)

    def set_trigger(self, trigger):
        self.trigger = trigger

    def set_effect(self, actual_action):
        self.effect = actual_action


class StateUsage(ElementDefinition, metaclass=MetaEClass):
    """Runtime registry entry for a StateDef's own nested substate (e.g.
    `Idle`, `Next`) — part of the StateDef's static structure, not a running
    instance. Per the SysML metamodel a StateUsage, like a StateDefinition,
    may itself declare entry/do/exit subactions; those live here. It carries
    no `type` and no dynamic "currently active" state of its own — that only
    exists on the ExecutableStateUsage instantiating the owning StateDef.
    """
    entry = EReference(eType=ActualAction, lower=0, upper=1, containment=False)
    do = EReference(eType=ActualAction, lower=0, upper=1, containment=False)
    exit = EReference(eType=ActualAction, lower=0, upper=1, containment=False)

    # Transitions that fire out of this substate (e.g. Idle's transition to
    # Next) — routed here by the owning StateDef's add_transition(), which
    # matches a built Transition's already-resolved `source` reference
    # against its substates (a TransitionUsage is a sibling FeatureMembership
    # of the StateDefinition, not nested inside the substate itself, so the
    # match can't be structural).
    contained_transitions = EReference(eType=Transition, lower=0, upper=-1, containment=False)

    def set_entry_action(self, actual_action):
        self.entry = actual_action

    def set_do_action(self, actual_action):
        self.do = actual_action

    def set_exit_action(self, actual_action):
        self.exit = actual_action

class StateDef(ElementDefinition, metaclass=MetaEClass):
    """Runtime registry entry for a StateDefinition: the reusable blueprint
    (top-level entry behavior plus nested substates, each with their own
    entry/do/exit and transitions — see StateUsage). Instantiated —
    possibly more than once — by an ExecutableStateUsage.
    """

    entry_action = EReference(eType=ActualAction, lower=0, upper=1, containment=False)
    default_transition = EReference(eType=Transition, lower=0, upper=1, containment=False)

    parameters = EReference(eType=Parameter, lower=0, upper=-1, containment=True)

    substates = EReference(eType=StateUsage, lower=0, upper=-1, containment=True)

    def add_parameter(self, parameter):
        self.parameters.append(parameter)

    def set_entry_action(self, actual_action):
        self.entry_action = actual_action

    def add_state(self, state_usage):
        self.substates.append(state_usage)

    def get_substate(self, qualified_name):
        """Resolves a substate by qualified name (e.g. a Transition's
        source/target Reference) against this StateDef's own substates.
        Linear scan, same shape as LookupTable.get_reference — substates
        are locally owned, not registered in a shared table.
        """
        for substate in self.substates:
            if substate.qualified_name == qualified_name:
                return substate
        return None

    def add_transition(self, transition):
        """Routes a built Transition to where it belongs.

        No trigger means the single unconditional transition fired right
        after entry completes. Otherwise, it belongs to whichever substate's
        contained_transitions its already-resolved `source` reference names
        — silently dropped if that doesn't match any known substate (e.g. a
        malformed model), same as an unresolved Reference elsewhere.
        """
        if transition.trigger is None:
            self.default_transition = transition
            return
        if transition.source is None:
            return
        substate = self.get_substate(transition.source.qualified_name)
        if substate is not None:
            substate.contained_transitions.append(transition)


class ExecutableStateUsage(ElementDefinition, metaclass=MetaEClass):
    """Runtime registry entry for a StateUsage declared outside any
    StateDefinition (e.g. `main : MySimulationDefinition`) — an actual,
    independently running instance of a state machine.

    `current`/`pending` (the dynamic "which substate is active" pointer and
    this instance's own mailbox) live here rather than on StateDef, since a
    single StateDef can be instantiated by more than one ExecutableStateUsage,
    each running independently and needing its own state.
    """

    # Reference to the StateDef this usage is typed by.
    state_def_origin = EReference(eType=Reference, lower=0, upper=1, containment=False)

    # The bound call-site arguments (e.g. conveyorBelt=cb1), each an
    # Argument holding the bound value. Same shape as ActualAction.arguments,
    # just binding a StateDef's formal parameters instead of an ActionDef's.
    arguments = EReference(eType=Argument, lower=0, upper=-1, containment=True)

    # Which of `type.substates` is presently active.
    current = EReference(eType=StateUsage, lower=0, upper=1, containment=False)

    # FIFO mailbox: items received while this instance was in some state,
    # not yet matched against a transition and consumed.
    pending = EReference(eType=ItemDef, lower=0, upper=-1, containment=False)

class PartDef(ElementDefinition, metaclass=MetaEClass):

    contained_perform_actions = EReference(eType=ActualAction, lower=0, upper=-1, containment=True)
    attributes = EReference(eType=AttributeUsageElement, lower=0, upper=-1, containment=True)

class CompositeCustomValue(Value):
    """A structured value made of named sub-values (e.g. placementCoordinate's
    `{x: 10.0, y: 0.0}`), rather than a single literal or reference. Reusable
    anywhere a Value is expected (Argument.value, Parameter.default_value,
    AttributeUsageElement.default_value), not just for attribute redefinition.

    `type` records which custom type this is an instance of (e.g.
    Common::FactoryCoordinate) using the same TypeRef shape (see
    _build_type_ref) already used for AttributeUsageElement.type/
    Parameter.type, rather than leaving it to be inferred from whatever
    happens to be holding this value.
    """
    type = EReference(eType=TypeRef, lower=0, upper=1)

    # Each element is an Argument (name + value) rather than a bare Value, so
    # sub-fields (x, y) carry their own names — an element's own `value` may
    # itself be a CompositeCustomValue, for further nesting.
    elements = EReference(eType=Argument, lower=0, upper=-1, containment=True)

class AttributeRedefinition(ElementDefinition, metaclass=MetaEClass):
    """A usage-site attribute override (SysML's `:>>` redefinition), e.g.
    cb1's `attribute :>> placementCoordinate { attribute :>> x = 10.0; ... }`.

    name/qualified_name (inherited from ElementDefinition) are taken from
    the *redefined* feature, not this redefinition's own AST node — a
    redefining feature is anonymous by SysML convention (`:>>` lets it reuse
    the redefined feature's name), so its own declaredName is always unset.
    """

    # Bare Reference to the attribute being redefined (e.g.
    # ConveyorBeltMachine::placementCoordinate, or FactoryCoordinate::x for a
    # nested sub-attribute). Attributes aren't registered in any LookupTable
    # (they live inside PartDef.attributes) — same deferred convention as
    # everywhere else, resolving this by qualified_name against the right
    # PartDef.attributes is left to whoever consumes it later.
    redefined_feature = EReference(eType=Reference, lower=0, upper=1, containment=False)

    # This redefinition's own value: a LiteralValue/ReferenceValue for a
    # primitive redefinition (e.g. x's `= 10.0`), or a CompositeCustomValue
    # for a composite one (e.g. placementCoordinate's own `{x, y}`).
    value = EReference(eType=Value, lower=0, upper=1, containment=True)

class PartInstantiation(ElementDefinition, metaclass=MetaEClass):

    # Reference to the PartDef this usage is typed by
    part_def_origin = EReference(eType=Reference, lower=0, upper=1, containment=False)

    # This usage's own attribute redefinitions (e.g. cb1's placementCoordinate
    # override).
    attribute_redefinitions = EReference(eType=AttributeRedefinition, lower=0, upper=-1, containment=True)

class SysmlRuntimeState(RuntimeStateElement, metaclass=MetaEClass):

    lookup_table_item_defs = EReference(eType=LookupTable, lower=0, upper=1, containment=True)
    lookup_table_part_defs = EReference(eType=LookupTable, lower=0, upper=1, containment=True)
    lookup_table_enum_defs = EReference(eType=LookupTable, lower=0, upper=1, containment=True)
    lookup_table_state_defs = EReference(eType=LookupTable, lower=0, upper=1, containment=True)
    lookup_table_action_defs = EReference(eType=LookupTable, lower=0, upper=1, containment=True)
    lookup_table_attribute_defs = EReference(eType=LookupTable, lower=0, upper=1, containment=True)

    # StateUsages declared outside any StateDefinition (e.g. `main :
    # MySimulationDefinition`) — actual instances of a state machine, as
    # opposed to a StateDefinition's own nested substates (e.g. Idle/Next),
    # which live in StateDef.substates instead and never have a type of
    # their own by modeling convention. This will be treated as state machines that must be executed
    lookup_table_executable_state_usages = EReference(eType=LookupTable, lower=0, upper=1, containment=True)

    # PartUsages declared directly under a package/namespace (e.g. `cb1 :
    # ConveyorBeltMachine` in Main) — actual instances of a part, as opposed
    # to PartDef (the shared blueprint each PartInstantiation points back at
    # via part_def_origin).
    lookup_table_part_instantiations = EReference(eType=LookupTable, lower=0, upper=1, containment=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lookup_table_action_defs = LookupTable()
        self.lookup_table_item_defs = LookupTable()
        self.lookup_table_state_defs = LookupTable()
        self.lookup_table_enum_defs = LookupTable()
        self.lookup_table_attribute_defs = LookupTable()
        self.lookup_table_part_defs = LookupTable()
        self.lookup_table_executable_state_usages = LookupTable()
        self.lookup_table_part_instantiations = LookupTable()

    def add_action_def(self, action_def):
        self.lookup_table_action_defs.set_reference(action_def.qualified_name, action_def)

    def add_item_def(self, item_def):
        self.lookup_table_item_defs.set_reference(item_def.qualified_name, item_def)

    def add_state_def(self, state_def):
        self.lookup_table_state_defs.set_reference(state_def.qualified_name, state_def)

    def add_enum_def(self, enum_def):
        self.lookup_table_enum_defs.set_reference(enum_def.qualified_name, enum_def)

    def add_attribute_def(self, attribute_def):
        self.lookup_table_attribute_defs.set_reference(attribute_def.qualified_name, attribute_def)

    def add_part_def(self, part_def):
        self.lookup_table_part_defs.set_reference(part_def.qualified_name, part_def)

    def add_executable_state_usage(self, usage):
        self.lookup_table_executable_state_usages.set_reference(usage.qualified_name, usage)

    def add_part_instantiation(self, instantiation):
        self.lookup_table_part_instantiations.set_reference(instantiation.qualified_name, instantiation)

def _resolve_definition(tables, type_node):
    """Looks up the ElementDefinition registered under `type_node`'s qualified
    name in any of `tables`, if any (e.g. a scalar-typed feature resolves to
    None, since no LookupTable holds an entry for it).

    Unresolved proxies (e.g. a feature typed by a KerML library element that
    isn't part of this document) are skipped rather than dereferenced, since
    resolving them would try to load an external resource the loader never
    registered; they can never match a locally-registered Definition anyway.
    """
    if type_node is None:
        return None
    if isinstance(type_node, EProxy) and not type_node.resolved:
        return None
    name = qualified_name(type_node)
    for table in tables:
        reference = table.get_reference(name)
        if reference is not None:
            return reference.element_type
    return None
