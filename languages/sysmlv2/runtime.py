from pyecore.ecore import MetaEClass, EAttribute, EReference, EString, EObject

from core.language import AbstractSyntaxElement, RuntimeStateElement

class ElementDefinition(RuntimeStateElement, metaclass=MetaEClass):
    """Runtime registry entry for a named SysML Definition.

    Built once when a Namespace is evaluated, so the rest of the AST can
    resolve a Definition by qualified name during execution instead of
    re-walking the model. `definition` points back at the syntax.py AST node
    (e.g. an ActionDefinition) this entry was built from; the structural
    interpretation of that node stays in its own evaluate(), not here.
    """

    qualified_name = EAttribute(eType=EString, lower=0, upper=1, containment=False)
    definition = EReference(eType=AbstractSyntaxElement, lower=0, upper=1, containment=False)


class Reference(ElementDefinition, metaclass=MetaEClass):
    element_type = EReference(eType=ElementDefinition, lower=0, upper=1, containment=False)

class LookupTable(EObject, metaclass=MetaEClass):
    references = EReference(eType=Reference, lower=0, upper=-1, containment=True)

    def get_reference(self, name):
        for b in self.references:
            if b.name == name:
                return b
        return None

    def has_reference(self, name):
        return self.get_reference(name) is not None

    def set_reference(self, name, value):
        reference = self.get_reference(name)
        if reference is not None:
            reference.value = value
        else:
            self.references.append(Reference(name=name, value=value))

class Parameter(ElementDefinition, metaclass=MetaEClass):
    """A named parameter slot: either a formal parameter declared on an
    ActionDef/StateDef (e.g. Print's `msg`, `value` unset), or a bound
    argument at a specific PerformActionUsage call site (`value` set to the
    AST literal/expression node it was bound to, `type` pointing back at the
    formal Parameter it fulfills).
    """
    type = EReference(eType=ElementDefinition, lower=0, upper=1, containment=False)
    default_value = EReference(eType=EObject, lower=0, upper=1, containment=False)

class Argument(ElementDefinition, metaclass=MetaEClass):
    """A named parameter slot: either a formal parameter declared on an
    ActionDef/StateDef (e.g. Print's `msg`, `value` unset), or a bound
    argument at a specific PerformActionUsage call site (`value` set to the
    AST literal/expression node it was bound to, `type` pointing back at the
    formal Parameter it fulfills).
    """
    value = EReference(eType=EObject, lower=0, upper=1, containment=False)


class ActionDef(ElementDefinition, metaclass=MetaEClass):
    """Runtime registry entry for an ActionDefinition."""

    parameters = EReference(eType=Parameter, lower=0, upper=-1, containment=True)


class ActualAction(ElementDefinition, metaclass=MetaEClass):
    """A single performance/call occurrence of an ActionDef (e.g. `pEntry`
    performing `Print`), analogous to how StateUsage is the running
    occurrence of a StateDef.
    """

    # Which ActionDef this call performs. None if it doesn't resolve.
    action_def = EReference(eType=ActionDef, lower=0, upper=1, containment=False)

    # The bound call-site arguments (e.g. msg="Entry"), each a Parameter
    # whose `type` points back at the formal Parameter it fulfills.
    arguments = EReference(eType=Argument, lower=0, upper=-1, containment=True)


class ItemDef(ElementDefinition, metaclass=MetaEClass):
    """Runtime registry entry for an ItemDefinition (a message/event type)."""

    # TODO: attributes, once AttributeDefinition/AttributeUsage support lands.
    pass

class StateUsage(ElementDefinition, metaclass=MetaEClass):
    """Runtime registry entry for a StateUsage: a running occurrence of a
    state — either a nested substate declared by a StateDef (e.g. `Idle`) or
    a top-level usage explicitly typed by one (e.g. `main` : MySimulationDefinition).

    `current`/`pending` (the dynamic "which substate is active" pointer and
    this instance's own mailbox) live here rather than on StateDef, since a
    single StateDef can be instantiated by more than one StateUsage, each
    running independently and needing its own state.
    """

    # The StateDef this usage is typed by. None for an anonymous nested
    # substate (e.g. Idle/Next), which belongs to its owning StateDef
    # without being typed by a StateDefinition of its own.
    type = EReference(eType=None, lower=0, upper=1, containment=False)

    # `StateUsage` isn't bound yet while its own class body executes, so this
    # self-referencing feature is declared untyped here and patched below.
    current = EReference(eType=None, lower=0, upper=1, containment=False)

    # FIFO mailbox: items received while this instance was in some state,
    # not yet matched against a transition and consumed.
    pending = EReference(eType=ItemDef, lower=0, upper=-1, containment=False)


# Patched in place (not replaced) so the name binding `_promote` assigned to
# each feature at class-creation time is preserved. Mirrors how
# tools/load_xmi_with_syntax.py repairs pyecoregen's untyped references by
# mutating `feature.eType` rather than reassigning the descriptor.
StateUsage.current.eType = StateUsage


class Transition(RuntimeStateElement, metaclass=MetaEClass):
    """A single transition declared by a StateDef, from one of its
    StateUsage substates to another.

    Built once from a TransitionUsage's source/trigger/target/effect. Firing
    it (matching an incoming item against `trigger`, running `effect`, moving
    the running StateUsage's `current` to `target`) is a dispatch concern
    left for later; this only holds the structure needed to find and fire one.
    """

    definition = EReference(eType=AbstractSyntaxElement, lower=0, upper=1, containment=False)

    # The StateUsage substate this transition fires out of (e.g. Idle).
    source = EReference(eType=StateUsage, lower=0, upper=1, containment=False)

    # None means an unconditional/completion transition (e.g. the one fired
    # right after MySimulationDefinition's entry action finishes).
    trigger = EReference(eType=ItemDef, lower=0, upper=1, containment=False)

    # The effect PerformActionUsage AST node, if any, evaluated when this
    # transition fires. None means no effect.
    effect = EReference(eType=Reference, lower=0, upper=1, containment=False)

    target = EReference(eType=StateUsage, lower=1, upper=1, containment=False)

class StateDef(ElementDefinition, metaclass=MetaEClass):
    """Runtime registry entry for a StateDefinition: the reusable blueprint
    (entry/do/exit behavior, nested substates, transitions between them).
    Instantiated — possibly more than once — by a StateUsage.
    """

    entry = EReference(eType=Reference, lower=0, upper=1, containment=False)
    do = EReference(eType=Reference, lower=0, upper=1, containment=False)
    exit = EReference(eType=Reference, lower=0, upper=1, containment=False)

    parameters = EReference(eType=Parameter, lower=0, upper=-1, containment=True)

    substates = EReference(eType=StateUsage, lower=0, upper=-1, containment=True)


# StateDef didn't exist yet while StateUsage's class body executed.
StateUsage.type.eType = StateDef


class SysmlRuntimeState(RuntimeStateElement, metaclass=MetaEClass):

    lookup_table_item_defs = EReference(eType=LookupTable, lower=0, upper=-1, containment=True)
    lookup_table_part_defs = EReference(eType=LookupTable, lower=0, upper=-1, containment=True)
    lookup_table_enum_defs = EReference(eType=LookupTable, lower=0, upper=-1, containment=True)
    lookup_table_state_defs = EReference(eType=LookupTable, lower=0, upper=-1, containment=True)
    lookup_table_action_defs = EReference(eType=LookupTable, lower=0, upper=-1, containment=True)
    lookup_table_attribute_defs = EReference(eType=LookupTable, lower=0, upper=-1, containment=True)