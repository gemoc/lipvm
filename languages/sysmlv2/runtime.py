import logging
from collections import deque
from enum import Enum
from typing import Optional

from pyecore.ecore import MetaEClass, EAttribute, EReference, EString, EObject, EProxy, EEnum

from core.language import AbstractSyntaxElement, RuntimeStateElement, RuntimeState
from core.operation import operation
from languages.sysmlv2.runtime_utility import ScalarType, _LITERAL_PYTHON_CONVERTERS, TypeKind, ParamDirection, \
    _BINARY_OPERATORS, _SCALAR_TYPE_BY_NAME
from languages.sysmlv2.sysml_utility_classes import qualified_name
from languages.sysmlv2.simulation_models.facade_proxy import PartNotReadyError, SimulationSnapshot, SimulationBridge
from languages.sysmlv2.simulation_models.generic import ActionSimulationModel
from languages.sysmlv2.simulation_models.registry import scan_for_subclasses

logger = logging.getLogger(__name__)

def _simulation_model_registry() -> dict:
    """Maps each concrete ActionSimulationModel subclass's name (e.g. "Print")
    to the class itself. Thin wrapper around the shared, reusable
    simulation_models scanner (also used for PartSimulationModel lookups) --
    see scan_for_subclasses for the caching/scanning details.
    """
    return scan_for_subclasses(ActionSimulationModel)

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

class Reference(ElementDefinition, metaclass=MetaEClass):

    '''
    An element representing a reference to another runtime state elements.
    It uses the qualified_name attribute as the main identifier to locate the original element
    '''
    reference_type = EAttribute(eType=EString, lower=1, upper=1)

class Value(RuntimeStateElement, metaclass=MetaEClass):
    # An abstract class to specify a value

    def evaluate(self, runtime: RuntimeState, current: "ExecutableStateUsage" = None, snapshot_from_bridge:
            SimulationSnapshot = None):
        """Resolves this Value to its actual runtime result — e.g. a
        literal's own payload, a dereferenced Reference, or (for
        AttributeReference/BinaryExpression) a looked-up/computed result.
        Deliberately NOT @operation-decorated (unlike ActualAction.evaluate()/
        Transition.evaluate()/etc., which the VM steps through): a Value
        tree is a pure, side-effect-free read/computation with nothing to
        interleave mid-evaluation, so it runs eagerly to a plain Python
        value in one call — no Operation chain for a caller to drain.

        `current` is the scope used to resolve this Value when it is being
        evaluated. It can be mandatory (e.g., for resolving
        AttributeReference to resolve a formal parameter) or optional (e.g., LiteralValue) depending
        on the subclasses.

        `snapshot_from_bridge` is the values from Simulation, particularly important if
        some values refer to the attribute of Parts that are mutated by the Simulation model. For values that are
        unrelated with the attributes of a part, they will not use this.

        Placeholder only on this base class. See memory: todo-actualaction-resolution-pipeline
        for the broader execution/resolution pipeline this is part of.
        """
        raise NotImplementedError('Value.evaluate() not yet implemented')

class LiteralValue(Value):
    el = EAttribute(eType=EString, lower=1, upper=1)
    scalar_type = EAttribute(eType=ScalarType, lower=0, upper=1)

    def evaluate(self, runtime: RuntimeState, current: "ExecutableStateUsage" = None, snapshot_from_bridge:
        SimulationSnapshot = None):
        """Converts `el` (always a string, per _literal_value()'s str(node.value)
        encoding in syntax.py) back to the Python type `scalar_type` names --
        not the raw string -- so a BinaryExpression comparing this against a
        live attribute's actual Python value (e.g. a real bool from
        AttributeReference.evaluate()) compares like-for-like instead of
        `True == "True"` (always False). _LITERAL_PYTHON_CONVERTERS is
        defined later in this module (shared with _custom_attribute_value())
        but resolved at call time, so the forward reference is safe.
        """
        return _LITERAL_PYTHON_CONVERTERS.get(self.scalar_type, str)(self.el)


# Maps a Reference's reference_type tag to the SysmlRuntimeState lookup
# table it's registered in -- only for reference_type tags confirmed by
# grepping syntax.py's _build_reference()/_resolve_feature_reference() call
# sites (so this doesn't claim to cover a tag nothing actually assigns).
# "Parameter" is deliberately absent: a formal parameter isn't registered
# in any global table at all -- it only has a concrete value relative to
# one specific running ExecutableStateUsage, so it can't be resolved this
# way regardless (see the context-based fallback below).
_LOOKUP_TABLE_NAME_BY_REFERENCE_TYPE = {
    "PartInstantiation": "lookup_table_part_instantiations",
    "PartDef": "lookup_table_part_defs",
    "ActionDef": "lookup_table_action_defs",
    "ItemDef": "lookup_table_item_defs",
    "StateDef": "lookup_table_state_defs",
    "CustomAttributeDefinition": "lookup_table_attribute_defs",
}

class ReferenceValue(Value):
    el = EReference(eType=Reference, lower=1, upper=1, containment=False)

    def evaluate(self, runtime: RuntimeState, current: "ExecutableStateUsage" = None, snapshot_from_bridge:
        SimulationSnapshot = None):
        """Resolves `el` (a bare Reference) by its `reference_type` tag --
        different kinds of reference need genuinely different resolution

        - "EnumerationUsage" (e.g. direction=DirectionKind::FORWARD, an
          action-argument binding) resolves all the way to the actual
          Python enum member, since that's what a caller like
          ActualAction.evaluate() needs to hand to a real method call
          (e.g. machine.moveToSensor(direction=DirectionKind.FORWARD)).
          scan_for_subclasses(Enum) is the same registry mechanism already
          used for PartSimulationModel/ActionSimulationModel/
          CustomAttributeModel, just scanning for Enum subclasses instead
          -- reused as-is rather than adding new machinery, and called
          directly here (not routed through the bridge), matching how
          ActionSimulationModel dispatch already works.
        - "Parameter" (e.g. conveyorBelt, a formal parameter name) is, by
          construction, only meaningful relative to whichever
          ExecutableStateUsage is currently evaluating it -- a formal
          parameter's own qualified name (e.g. "...::conveyorBelt") is
          never itself a lookup key in any global table. So this branch
          is selected purely by `reference_type` -- whether `current` is
          usable is a separate question, handled *inside* the branch, not
          a precondition for entering it (otherwise a missing `current`
          would silently fall through to the unrelated catch-all below,
          reporting the wrong cause). It resolves against
          `current.arguments`, the same lookup AttributeReference.evaluate()
          currently duplicates inline for its own `target`. Raises
          (with the specific reason -- no `current` at all, vs. `current`
          present but nothing bound under this name -- embedded in the
          message) rather than silently handing back the bare qualified
          name, which a caller (e.g. BinaryExpression) could otherwise
          compare against as if it were a real value.
        - Anything else, with a registered lookup table (today, just
          "PartInstantiation", e.g. conveyorBelt=cb1 -- confirmed by
          walking both real models, nothing else shows up) resolves to
          the actual registry record itself (e.g. the PartInstantiation),
          not just its qualified name -- these are absolute, globally
          registered names (cb1 is declared directly under package Main),
          so a flat table lookup is correct and doesn't depend on which
          instance is asking. Anything with neither a table entry nor
          "Parameter"/"EnumerationUsage" (none observed today) raises,
          naming the unrecognized reference_type and what's actually
          handled, for the same reason.
        """
        if self.el.reference_type == "EnumerationUsage":
            *_, enum_name, member_name = self.el.qualified_name.split("::")
            enum_class = scan_for_subclasses(Enum)[enum_name]
            return enum_class[member_name]

        if self.el.reference_type == "Parameter":
            if current is None:
                raise RuntimeError(
                    f"Cannot resolve parameter reference '{self.el.qualified_name}': "
                    f"evaluate() was called with current=None, but a Parameter reference "
                    f"can only be resolved against a running ExecutableStateUsage's own "
                    f"bound arguments."
                )
            param_name = self.el.qualified_name.split("::")[-1]
            binding = next((argument for argument in current.arguments if argument.name == param_name), None)
            if binding is None:
                raise LookupError(
                    f"No argument named '{param_name}' bound on '{current.qualified_name}' "
                    f"(available: {sorted(argument.name for argument in current.arguments)}) -- "
                    f"cannot resolve parameter reference '{self.el.qualified_name}'."
                )
            return binding.value.evaluate(runtime, current, snapshot_from_bridge)

        table_name = _LOOKUP_TABLE_NAME_BY_REFERENCE_TYPE.get(self.el.reference_type)
        if table_name is not None:
            record = getattr(runtime.sysml, table_name).get_reference(self.el.qualified_name)
            return record.element_type if record is not None else None

        raise LookupError(
            f"No resolution rule for reference_type '{self.el.reference_type}' "
            f"(qualified_name='{self.el.qualified_name}') -- handled types: "
            f"'EnumerationUsage', 'Parameter', {sorted(_LOOKUP_TABLE_NAME_BY_REFERENCE_TYPE)}."
        )

class AttributeReference(Value):
    """Reads an attribute's current value off whatever's bound to a formal
    parameter (e.g. conveyorBelt.conveyorSensSwap in an `accept when`
    guard) — distinct from ActualAction's target, which identifies a
    behavior to invoke rather than a value to read/compare.

    Both target and attribute are bare, unresolved References, same
    deferred convention as everywhere else: resolving target to a concrete
    PartInstantiation, and attribute to the matching entry in that
    instantiation's PartDef.attributes, is left to whoever evaluates this
    later.
    """
    target = EReference(eType=Reference, lower=0, upper=1, containment=False)
    attribute = EReference(eType=Reference, lower=0, upper=1, containment=False)

    def evaluate(self, runtime: RuntimeState, current: "ExecutableStateUsage" = None, snapshot_from_bridge:
        SimulationSnapshot = None):
        """Resolves `target` (the formal parameter, e.g. `conveyorBelt`) by
        wrapping it in a transient ReferenceValue and delegating to its own
        evaluate() -- `target` carries the same "Parameter" reference_type
        ReferenceValue already knows how to resolve against `current.arguments`
        (with the same informative errors on failure), so this no longer
        duplicates that lookup inline.

        Only reads `attribute` off the resolved value through the bridge if
        it actually resolved to a PartInstantiation -- the one case that
        genuinely has a live simulation counterpart to read an attribute
        from. Every model today binds `target` to a part (e.g.
        conveyorBelt=cb1), so this is what actually happens in practice,
        but nothing enforces a formal parameter must be bound to a part
        specifically -- if it resolved to something else (e.g. a plain
        scalar bound to that parameter instead), there's no "instance" to
        read an attribute off of, so the resolved value itself, whatever
        it is, is simply returned as-is rather than crashing on
        `.qualified_name` (which only a PartInstantiation actually has).
        """
        resolved = ReferenceValue(el=self.target).evaluate(runtime, current)
        if not isinstance(resolved, PartInstantiation):
            raise NotImplementedError('Currently, only handling a case where attribute reference involves'
                                      'Part Instantiation. Please handle it first before continuing.')
        attribute_name = self.attribute.qualified_name.split("::")[-1]
        return SimulationBridge.read_attribute_from_snapshot(
            snapshot_from_bridge, resolved.qualified_name, attribute_name)

class BinaryExpression(Value):
    """A binary operation over two sub-values (e.g. `conveyorBelt.
    conveyorSensFeed == true`, or `<left> and <right>` combining two such
    comparisons) — covers both `==`-style comparisons and boolean
    combinators (`and`/`or`/...) with the same shape, since both are just
    an operator plus two operands.

    left/right are typed as the generic Value base rather than any one
    subclass, so an operand may itself be a LiteralValue, an
    AttributeReference, or another BinaryExpression — this recursion is
    what lets a compound condition (e.g. an `and` of two `==` comparisons)
    fall out of the same shape without any extra machinery.
    """
    operator = EAttribute(eType=EString, lower=1, upper=1)
    left = EReference(eType=Value, lower=1, upper=1, containment=True)
    right = EReference(eType=Value, lower=1, upper=1, containment=True)

    def evaluate(self, runtime: RuntimeState, current: "ExecutableStateUsage" = None, snapshot_from_bridge:
        SimulationSnapshot = None):
        """Plain recursive calls -- `current` passed to both sub-evaluations
        unchanged (not re-resolved here), so an AttributeReference nested
        anywhere in left/right still resolves against the same running
        instance this whole expression is being evaluated for.
        """
        left = self.left.evaluate(runtime, current, snapshot_from_bridge)
        right = self.right.evaluate(runtime, current, snapshot_from_bridge)
        return _BINARY_OPERATORS[self.operator](left, right)

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

    # Which formal parameter this action is performed through, if any (e.g.
    # conveyorBelt for `do conveyorBelt.moveToSensor`) — None for a direct
    # action (e.g. pEntry performing Print). Resolving this to a concrete
    # PartInstantiation depends on which ExecutableStateUsage is actually
    # running (see its own `arguments`), so — same deferred convention as
    # action_def — it's left as a bare Reference, not resolved here.
    target = EReference(eType=Reference, lower=0, upper=1, containment=False)

    def evaluate(self, runtime: RuntimeState, current: "ExecutableStateUsage" = None):
        """Plain eager call, matching every other runtime record's evaluate()
        except ExecutableStateUsage's own (the one genuine VM-step boundary,
        see its docstring) -- @operation used to decorate this method, but
        nothing ever drained it lazily: ExecutableStateUsage's own reactive
        pass always called .execute() on the result immediately, in the same
        breath it was built, so the decorator bought only an extra
        build-then-immediately-unwrap indirection, not real steppability.
        Removed for the same reason BinaryExpression's own lazy left=/right=
        sub-operations were simplified back to plain recursive calls (see
        Value's own docstring) -- this codebase's one deliberate decision is
        that only ExecutableStateUsage.evaluate() is a real step; everything
        it triggers (entry/exit actions, transition effects, part
        instantiation) runs eagerly as an ordinary sub-call.

        Resolves action_def and binds each argument's Value, then performs
        the call. Two shapes, per `target`:

        - `target is None` (a direct action, e.g. `pEntry` performing
          `Print`): dispatches to the ActionSimulationModel subclass (under
          languages/sysmlv2/simulation_models) whose class name matches the
          resolved ActionDef's own name (e.g. "Print") -- unchanged from
          before.
        - `target is not None` (a chained action, e.g. `do conveyorBelt.
          moveToSensor`): resolves `target` (a "Parameter" reference, e.g.
          conveyorBelt) via ReferenceValue -- same resolution
          AttributeReference.evaluate() uses -- to the concrete
          PartInstantiation this is actually being performed on, then calls
          the real method through `SimulationBridge.call_action()`
          using `self.name` (e.g. "moveToSensor", the perform-action's own
          declared name -- NOT action_def.name, "MoveToSensor", which is
          the ActionDefinition's name and not what's callable on the
          PartSimulationModel).

        Argument values are resolved eagerly, via a plain Value.evaluate()
        call (no longer @operation-decorated -- see Value's own docstring).

        For the chained shape, bound arguments are merged from three layers,
        lowest priority first so a later layer's dict update wins ties:
        1. The resolved ActionDef's own formal-parameter defaults (e.g. a
           default on MoveToSensor's `direction` parameter, if any model
           ever declares one -- none do today).
        2. The PartDef-contained occurrence's own bound arguments (e.g. if
           ConveyorBeltMachine's own `perform action moveToSensor :
           MoveToSensor { ... }` declaration bound something itself --
           no model does today, but the mechanism doesn't assume it won't).
        3. This specific call site's own bound arguments (e.g.
           `direction=DirectionKind::FORWARD` directly on `do conveyorBelt.
           moveToSensor` -- the only layer any current model actually uses).
        """
        if self.action_def is None:
            # An empty ActualAction (e.g. a bare `entry;` with no body) --
            # see ActionUsage.to_actual_action()'s base case, which builds
            # exactly this shape on purpose. Nothing to dispatch to.
            return

        action_def_record = runtime.sysml.lookup_table_action_defs.get_reference(self.action_def.qualified_name)
        action_def = action_def_record.element_type if action_def_record is not None else None
        name = action_def.name if action_def is not None else None

        if self.target is None:
            bound = {argument.name: argument.value.evaluate(runtime, current) for argument in self.arguments}
            registry = _simulation_model_registry()
            if name not in registry:
                raise LookupError(
                    f"No ActionSimulationModel subclass named '{name}' found in simulation_models "
                    f"(available: {sorted(registry)})"
                )
            registry[name](**bound).evaluate()
            return

        part_instantiation = ReferenceValue(el=self.target).evaluate(runtime, current)
        if not isinstance(part_instantiation, PartInstantiation):
            raise NotImplementedError(
                f"'{self.qualified_name}' is performed through '{self.target.qualified_name}', which "
                f"resolved to a {type(part_instantiation).__name__!r}, not a PartInstantiation -- "
                f"dispatching a chained action to anything other than a live part isn't handled yet."
            )

        part_def_record = runtime.sysml.lookup_table_part_defs.get_reference(
            part_instantiation.part_def_origin.qualified_name)
        part_def = part_def_record.element_type if part_def_record is not None else None
        origin_occurrence = next(
            (perform_action for perform_action in part_def.contained_perform_actions
             if perform_action.qualified_name == self.qualified_name),
            None,
        ) if part_def is not None else None

        bound = {}
        if action_def is not None:
            for parameter in action_def.parameters:
                if parameter.direction == ParamDirection.OUT:
                    # An `out` parameter's default_value is its initial
                    # *output* value (e.g. Grip's `out attribute
                    # vacuumActValve : Boolean = true`), not an argument
                    # the callee should receive -- including it here would
                    # pass it straight through to the Python method as an
                    # unexpected keyword argument.
                    continue
                if parameter.default_value is not None:
                    bound[parameter.name] = parameter.default_value.evaluate(runtime, current)
        if origin_occurrence is not None:
            for argument in origin_occurrence.arguments:
                bound[argument.name] = argument.value.evaluate(runtime, current)
        for argument in self.arguments:
            bound[argument.name] = argument.value.evaluate(runtime, current)

        SimulationBridge.call_action(runtime.channel, part_instantiation.qualified_name, self.name, **bound)

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

    signal_origin = EReference(eType=Reference, lower=0, upper=1, containment=True)

    def evaluate(self, item: "ItemDef") -> bool:
        """Returns whether `item` (a pending ItemDef popped off
        ExecutableStateUsage.pending, see _check_and_fire()) is the signal
        this trigger fires on — the only thing a signal trigger's firing
        depends on, so this is all _match_transition() needs from it,
        mirroring TransitionTriggerByWhenCondition.evaluate() one class
        over (that one takes runtime/current instead of item, since a
        when-condition's firing depends on live attribute state rather
        than an incoming item -- each trigger kind's evaluate() takes
        whatever it actually needs, not a shared signature).
        """
        return self.signal_origin.qualified_name == item.qualified_name

class TransitionTriggerByWhenCondition(TransitionTrigger, metaclass=MetaEClass):

    condition = EReference(eType=Value, lower=0, upper=1, containment=True)

    def evaluate(self, runtime: RuntimeState, current: "ExecutableStateUsage", latest_simulation_snapshot:
    SimulationSnapshot) -> bool:
        """Evaluates `condition` to a plain bool, right now -- Value.evaluate()
        is a plain eager call (not @operation-decorated), so this needs no
        Operation-chain draining, just a bool() around whatever it returns.
        Kept as its own method (mirroring _match_transition()'s own
        plain-eager style one level up) since it's consumed as an
        immediate yes/no by whoever decides whether to fire a transition.

        `PartNotReadyError` (facade_proxy.py) means a nested
        `AttributeReference` asked about a part the owning thread hasn't
        finished instantiating/publishing yet -- an ordinary startup race,
        not a real failure (see that exception's docstring). Treated the
        same as any other not-yet-satisfied condition: this trigger just
        doesn't fire this tick, and gets re-checked the next one, same as
        it would for a guard that's legitimately false for any other
        reason.
        """
        try:
            return bool(self.condition.evaluate(runtime, current, latest_simulation_snapshot))
        except PartNotReadyError:
            return False

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

    def evaluate(self, runtime: RuntimeState, current: "ExecutableStateUsage" = None):

        if self.effect is not None:
            return self.effect.evaluate(runtime, current)

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
    pending = EReference(eType=ItemDef, lower=0, upper=-1, containment=False, unique=False)

    @operation(is_step=True)
    def evaluate(self, runtime: RuntimeState):
        """The one genuine VM-step boundary in this whole reactive pipeline
        -- `is_step=True` is what makes VirtualMachine.step() stop right
        before the *next* ExecutableStateUsage's own evaluate(), so one
        step corresponds to exactly one instance's reactive pass. Everything
        this method triggers below (entry/exit actions, transition effects,
        part instantiation) runs as an ordinary eager sub-call, not a
        separately-stepped Operation -- see ActualAction.evaluate()'s own
        docstring for why that used to be otherwise and no longer is.
        """

        #Step 1: Only start executing this ExecutableStateUsage if the StateDef is resolved, otherwise just return None
        record_referenced_state_def: Record = runtime.sysml.lookup_table_state_defs.get_reference(
            self.state_def_origin.qualified_name)
        if record_referenced_state_def is None:
            return None

        original_state_def: StateDef = record_referenced_state_def.element_type
        if original_state_def is None:
            return None

        # Step 2: Run the default entry action and transition, only if the
        # current state is still none, otherwise go straight for the usual behavior
        if self.current is None:
            self._run_entry_behaviour(runtime, original_state_def)

        # Step 3: Fire one transition, if one matches
        self._check_and_fire(runtime, original_state_def)

    def _run_entry_behaviour(self, runtime: RuntimeState, original_state_def: StateDef):

        #Step 1: Run the entry action
        if original_state_def.entry_action is not None:
            original_state_def.entry_action.evaluate(runtime, self)

        #Step 2: start the transition
        transition = original_state_def.default_transition
        if transition is not None:
            target_state = original_state_def.get_substate(transition.target.qualified_name)
            self.current = target_state

            #Step 3: run the entry action of the newly-entered substate itself (e.g. Start's own
            # `entry conveyorBelt.moveToSensor {...}`) -- distinct from original_state_def.entry_action
            # above (the StateDef's own top-level entry, e.g. ConveyorBeltComplexMissionTwo's bare
            # `entry;`). Previously only _fire_transition() ran a target substate's entry -- meaning
            # the very first transition (StateDef default -> its first substate, handled here instead)
            # silently skipped it. Run after self.current is reassigned, not before, so it fires
            # only once self.current genuinely reflects target_state, matching _fire_transition()'s
            # own ordering for every later transition.
            if target_state.entry is not None:
                target_state.entry.evaluate(runtime, self)

    def _find_matching_transition(self, runtime_state: RuntimeState, current_context: "ExecutableStateUsage"):
        """Returns the first transition out of `current` whose trigger
        actually fires, checking TransitionTriggerBySignal against
        `processed_item` and TransitionTriggerByWhenCondition against live
        attribute state -- keeps scanning past a transition whose trigger
        doesn't match (rather than giving up after the first one checked),
        since a state can have more than one outgoing transition (e.g.
        Continue has both a when-condition and a signal transition).
        `processed_item` is None whenever `pending` is empty -- expected
        now that _check_and_fire() runs every tick regardless of pending
        (so when-condition transitions get checked on their own, not just
        when a signal happens to also be waiting). A TransitionTriggerBySignal
        can never fire without an incoming item, so it's skipped entirely
        in that case rather than evaluated against None.
        """

        # Treat the pending attribute as a queue, take the first element and remove it from the queue
        processed_item: Optional[ItemDef] = None
        if current_context.pending:
            processed_item = current_context.pending[0]
            current_context.pending.remove(processed_item)

        # Captured lazily, on the first TransitionTriggerByWhenCondition
        # actually reached below -- not unconditionally up front -- so a
        # state whose transitions are all plain signal triggers never touches
        # the channel at all. Every when-condition guard checked in
        # this pass still shares the exact same snapshot object once
        # captured, same guarantee as before.
        latest_simulation_snapshot: Optional[SimulationSnapshot] = None
        snapshot_captured = False

        for transition in self.current.contained_transitions:
            trigger = transition.trigger
            if isinstance(trigger, TransitionTriggerBySignal):
                if processed_item is not None and trigger.evaluate(processed_item):
                    return transition
            elif isinstance(trigger, TransitionTriggerByWhenCondition):
                if not snapshot_captured:
                    latest_simulation_snapshot = runtime_state.channel.latest_snapshot.read()
                    snapshot_captured = True
                if trigger.evaluate(runtime_state, current_context, latest_simulation_snapshot):
                    return transition

        if processed_item is not None:
            logger.warning(
                "%s: dropping pending item %s — no transition out of %s matches it",
                self.qualified_name, processed_item.qualified_name, self.current.qualified_name)

        return None

    def _check_and_fire(self, runtime: RuntimeState, original_state_def: StateDef):
        """One reactive pass: walks `pending` in FIFO order (oldest first)
        pop one item from pending, check if it matches any transition guard of the current state, and firing it if it is found.

        Any item scanned along the way that matches nothing is stale for
        this state: it's logged and dropped from `pending` rather than left
        to accumulate forever, since nothing will ever consume it once
        `current` has moved past the state that could have.
        """
        if self.current is None:
            return

        transition = self._find_matching_transition(runtime, self)
        if transition is not None:
            self._fire_transition(runtime, transition, original_state_def)

    def _fire_transition(self, runtime: RuntimeState, designated_transition: Transition, original_state_def: StateDef):

        current_state_usage: StateUsage = self.current

        #Step 1: run the exit action of the current StateUsage
        if current_state_usage.exit is not None:
            current_state_usage.exit.evaluate(runtime, self)

        #Step 2: run the transition effect
        designated_transition.evaluate(runtime, self)

        #Step 3: change the current pointer to the new StateUsage
        target_state: StateUsage = original_state_def.get_substate(designated_transition.target.qualified_name)
        self.current = target_state

        #Step 4: run the entry action of the newly appointed StateUsage
        if target_state.entry is not None:
            target_state.entry.evaluate(runtime, self)

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

def _custom_attribute_value(value: "CompositeCustomValue"):
    """Converts a CompositeCustomValue (e.g. placementCoordinate's
    {x: 10.0, y: 0.0, degrees: 0.0}) into (class_name, values) -- generic
    over which custom attribute type this is, not just FactoryCoordinate,
    so a second custom attribute needs no changes on this side. class_name
    is the bare name of the CustomAttributeDefinition this value is typed
    by (e.g. "FactoryCoordinate"); resolving it to the matching Python
    class (via scan_for_subclasses(CustomAttributeModel)) and constructing
    it from `values` is left to whoever consumes this (currently only
    FischertechnikBridge.instantiate()), same deferred-resolution
    convention used everywhere else in this module.
    """
    class_name = value.type.reference_type.qualified_name.split("::")[-1]
    values = {
        element.name: _LITERAL_PYTHON_CONVERTERS.get(element.value.scalar_type, str)(element.value.el)
        for element in value.elements
    }
    return class_name, values

class PartInstantiation(ElementDefinition, metaclass=MetaEClass):

    # Reference to the PartDef this usage is typed by
    part_def_origin = EReference(eType=Reference, lower=0, upper=1, containment=False)

    # This usage's own attribute redefinitions (e.g. cb1's placementCoordinate
    # override).
    attribute_redefinitions = EReference(eType=AttributeRedefinition, lower=0, upper=-1, containment=True)

    def evaluate(self, runtime: RuntimeState):
        """Ensures this usage's live simulation counterpart exists, via
        SimulationBridge -- idempotency is entirely the bridge's
        concern (backed by Factory's own machine registry, keyed by name),
        not something PartInstantiation tracks itself; no field is stored
        on self. Later code (e.g. ActualAction/AttributeReference)
        resolves its target to a PartInstantiation and calls the bridge
        directly with self.qualified_name, rather than routing through
        this method again.

        Handles any redefinition whose value is a CompositeCustomValue
        (e.g. cb1's placementCoordinate) generically -- not just
        "placementCoordinate" by name -- so a second custom attribute
        needs no changes here. A plain-scalar redefinition (e.g. a bare
        `attribute :>> someInt = 5;`, no model has one today) is still
        left unhandled, matching the previous narrowness; only composite
        ones are simulation-bridge concerns. Passes plain values to the
        bridge (not the raw AttributeRedefinition/CompositeCustomValue AST
        nodes), so the simulation side never needs to understand SysML's
        shapes either -- only which Python class (see
        FischertechnikBridge.instantiate()) mirrors the custom type named.
        """
        part_def_name = self.part_def_origin.qualified_name.split("::")[-1]

        attrs = {}
        for redefinition in self.attribute_redefinitions:
            if isinstance(redefinition.value, CompositeCustomValue):
                attrs[redefinition.name] = _custom_attribute_value(redefinition.value)

        SimulationBridge.instantiate(runtime.channel, self.qualified_name, part_def_name, **attrs)

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
