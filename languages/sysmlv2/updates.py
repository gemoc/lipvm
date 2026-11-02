"""Updates derived from the sysmlv2 language.

Unlike minilogo/robot -- whose stepped operations carry the AST nodes they
edit, so an AST edit is picked up as the program runs -- sysmlv2 walks its AST
**once** into a materialized runtime registry (`SysmlRuntimeState`: the
`StateDef`/`Transition`/`ActualAction`/`ExecutableStateUsage` records). Behavior
then runs off that registry, so a hot update here is a **registry migration**:
the meaningful work is in `apply(runtime)`, which reconciles the runtime
records -- editing the AST afterward would not change anything running.

The checkpoint is the state-machine reactive pass. A top-level `StateUsage`
(`main : MySimulationDefinition`) is marked as an `UpdateBeforePoint` (see
syntax.py), and its `ExecutableStateUsage` step now resolves back to that AST
node (via `RuntimeStateElement.ast_node()`), so an update is taken into account
just before a reactive pass -- gated by the update's own `condition`.

The domain-safe condition is **quiescence**: every state machine settled in a
substate with an empty mailbox, so the registry is never rewired mid-reaction
(the analog of minilogo's "pen up"). These updates carry no edit_script -- the
change lives entirely in the migration.

Updates that change the parts of the running system are gated by **execution
tranquility** instead (`TranquilUpdate`): every part the update affects must
satisfy its part def's `#Tranquility` constraints (see
Language-Safe-and-Execution-Tranquility-points.md). The checkpoint stays the
language safe point; tranquility is the `condition`.
"""
from typing import Optional

from core.edit import Update
from core.language import RuntimeState

from languages.sysmlv2 import runtime as rt
from languages.sysmlv2.syntax import StateUsage


def _executable_state_usages(runtime: RuntimeState):
    return [record.element_type
            for record in runtime.sysml.lookup_table_executable_state_usages.records]


def _part_instantiation(runtime: RuntimeState, part_usage_qn: str) -> rt.PartInstantiation:
    record = runtime.sysml.lookup_table_part_instantiations.get_reference(part_usage_qn)
    if record is None:
        raise LookupError(f"{part_usage_qn!r} is not a part usage of the running model.")
    return record.element_type

class SysmlUpdate(Update):
    """Base for sysmlv2 updates: the checkpoint is a state-machine reactive
    pass, so checkpoint_type() is the top-level StateUsage AST node."""

    def checkpoint_type(self) -> type:
        return StateUsage


class QuiescentUpdate(SysmlUpdate):
    """A sysmlv2 update only safe to apply while every state machine is
    quiescent -- each ExecutableStateUsage settled in a substate (`current`
    set) with an empty `pending` mailbox -- so the registry is not rewired
    while a machine is mid-reaction."""

    def condition(self, runtime: RuntimeState) -> bool:
        usages = _executable_state_usages(runtime)
        return bool(usages) and all(
            usage.current is not None and len(usage.pending) == 0
            for usage in usages
        )


def _transition(runtime: RuntimeState, state_def_qn: str, source_substate_qn: str, index: int):
    state_def = runtime.sysml.lookup_table_state_defs.get_reference(state_def_qn).element_type
    substate = state_def.get_substate(source_substate_qn)
    return substate.contained_transitions[index]


class RemessageTransitionEffect(QuiescentUpdate):
    """Change the message a transition's effect prints (a Print action),
    migrating the registry `ActualAction` argument so the new message is used
    the next time the transition fires.

    Derived from the `Print(msg=...)` construct: the effect's bound argument is
    a `LiteralValue` whose `el` is the message string; mutating it in place is
    all that's needed, since `LiteralValue.evaluate` reads `el` at call time.
    """

    def __init__(self, state_def: str, source_substate: str, new_message: str,
                 argument_name: str = "msg", transition_index: int = 0, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state_def = state_def
        self._source_substate = source_substate
        self._new_message = new_message
        self._argument_name = argument_name
        self._transition_index = transition_index

    def apply(self, runtime: RuntimeState) -> None:
        transition = _transition(runtime, self._state_def, self._source_substate, self._transition_index)
        argument = next(a for a in transition.effect.arguments if a.name == self._argument_name)
        argument.value.el = self._new_message


class RerouteTransition(QuiescentUpdate):
    """Change where a transition goes, migrating the registry `Transition.target`
    reference to a different substate. `_fire_transition` resolves the target by
    qualified name, so mutating it in place reroutes the machine on the next
    firing.
    """

    def __init__(self, state_def: str, source_substate: str, new_target_substate: str,
                 transition_index: int = 0, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state_def = state_def
        self._source_substate = source_substate
        self._new_target_substate = new_target_substate
        self._transition_index = transition_index

    def apply(self, runtime: RuntimeState) -> None:
        transition = _transition(runtime, self._state_def, self._source_substate, self._transition_index)
        transition.target.qualified_name = self._new_target_substate

class TranquilUpdate(SysmlUpdate):
    """A sysmlv2 update only applied while every element it affects is
    tranquil, each element deciding what that means through its own
    is_tranquil() (for a PartInstantiation: its part def's #Tranquility
    conditions plus its own; a part without any is always tranquil).
    Replaces QuiescentUpdate's "all machines settled" for updates that change
    parts of the running system.

    A subclass states what it affects through affected_elements(), derived
    from the model element it changes, so the VM can ask before applying it.
    """

    def affected_elements(self, runtime: RuntimeState) -> list[rt.TranquilityHolder]:
        """The running elements this update changes."""
        raise NotImplementedError("A TranquilUpdate must declare its affected_elements()")

    def condition(self, runtime: RuntimeState) -> bool:
        """To ensure that the update is safe, every element affected by this update should reach tranquility."""
        return all(element.is_tranquil(runtime)
                   for element in self.affected_elements(runtime))

    def check(self, runtime: RuntimeState) -> None:
        """Raises if this update can't be applied to `runtime` (e.g. the
        attribute it changes doesn't exist); changes nothing. Lets an
        AtomicUpdate check every member before applying any, and a driver
        reject an update before submitting it. Nothing to check by default.
        """
        raise NotImplementedError("A TranquilUpdate sub-class must implement a pre-check mechanism to ensure validity.")

    def apply(self, runtime: RuntimeState) -> None:
        raise NotImplementedError("A TranquilUpdate must declare the mechanism to apply changes to the current execution.")


class ChangeRuntimeAttributeValue(TranquilUpdate):
    """A runtime change: give an attribute of a running part usage (e.g.
    `Main::tokenDepo`'s `placementCoordinate`) a new value. `apply()` replaces
    the value of that usage's AttributeRedefinition in the registry.

    Runtime means the owner has a runtime record (a PartInstantiation), i.e.
    it is actually running. A part def owner is a design-time change, which
    propagates to every usage that doesn't redefine the attribute: a separate
    update class, so this one raises ValueError for it (see
    Language-Safe-and-Execution-Tranquility-points.md, Topic 10, "Runtime vs.
    design-time changes"). `new_value` is a registry Value
    (CompositeCustomValue for a structured attribute, LiteralValue for a
    scalar), keeping the update independent of domain types.
    """

    def __init__(self, owner: str, attribute: str, new_value: rt.Value, **kwargs) -> None:
        super().__init__(**kwargs)
        self._owner = owner
        self._attribute = attribute
        self._new_value = new_value

    def affected_elements(self, runtime: RuntimeState) -> list[rt.PartInstantiation]:
        if runtime.sysml.lookup_table_part_defs.get_reference(self._owner) is not None:
            raise ValueError(
                f"{self._owner!r} is a part def: changing its attribute value is a design-time "
                f"change, not a runtime one.")
        return [_part_instantiation(runtime, self._owner)]

    def _redefinition(self, runtime: RuntimeState) -> Optional[rt.AttributeRedefinition]:
        part = _part_instantiation(runtime, self._owner)
        redefinition = next((r for r in part.attribute_redefinitions if r.name == self._attribute), None)
        if redefinition is None:
            raise LookupError(
                f"{self._owner!r} doesn't redefine {self._attribute!r} "
                f"(redefined: {sorted(r.name for r in part.attribute_redefinitions)}).")
        return redefinition

    def check(self, runtime: RuntimeState) -> None:
        """Raises LookupError if the owner isn't a running part usage or
        doesn't redefine the attribute."""
        self._redefinition(runtime)

    def apply(self, runtime: RuntimeState) -> None:
        self._redefinition(runtime).value = self._new_value


class AddPartInstantiation(TranquilUpdate):
    """A runtime change: add a running part usage (e.g. a second
    `Main::tokenDepo2 : TokenDepoMachine`) with its configured values.
    `apply()` adds a PartInstantiation to the registry, shaped like one the
    build pass makes from `part tokenDepo2 : TokenDepoMachine { attribute :>>
    placementCoordinate { ... } }`; the part-table observer then sends it to
    the simulation through the SynchronizationManager.

    Always tranquil: a new part has no running state, no behaviour in
    progress and nothing bound to it, so nothing can be inconsistent with it
    and only the language safe point applies (`affected_elements()` is empty).
    It is still a TranquilUpdate, so it can be an AtomicUpdate member.

    `attribute_values` maps attribute names of the part def to registry
    Values; only composite values (CompositeCustomValue) for now, the only
    kind the simulation receives. The new part carries no #Tranquility
    constraints of its own (its part def's still apply).
    """

    def __init__(self, qualified_name: str, part_def: str, attribute_values: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self._qualified_name = qualified_name
        self._part_def = part_def
        self._attribute_values = dict(attribute_values)

    def affected_elements(self, runtime: RuntimeState) -> list[rt.TranquilityHolder]:
        return []

    def check(self, runtime: RuntimeState) -> None:
        """Raises ValueError if the name is taken, LookupError if the part def
        isn't registered or doesn't declare an attribute, TypeError for a
        value that isn't composite."""
        if runtime.sysml.lookup_table_part_instantiations.get_reference(self._qualified_name) is not None:
            raise ValueError(f"{self._qualified_name!r} is already a part usage of the running model.")

        record = runtime.sysml.lookup_table_part_defs.get_reference(self._part_def)
        if record is None:
            raise LookupError(f"{self._part_def!r} is not a registered PartDef.")

        declared = {attribute.name for attribute in record.element_type.attributes}
        for attr_name, value in self._attribute_values.items():
            if attr_name not in declared:
                raise LookupError(
                    f"{self._part_def!r} doesn't declare {attr_name!r} (declared: {sorted(declared)}).")
            if not isinstance(value, rt.CompositeCustomValue):
                raise TypeError(
                    f"{self._qualified_name!r}'s {attr_name!r}: only composite values can be sent "
                    f"to the simulation, got {type(value).__name__}.")

    def apply(self, runtime: RuntimeState) -> None:
        self.check(runtime)
        part_def = runtime.sysml.lookup_table_part_defs.get_reference(self._part_def).element_type
        declared = {attribute.name: attribute.qualified_name for attribute in part_def.attributes}

        part = rt.PartInstantiation(
            name=self._qualified_name.split("::")[-1], qualified_name=self._qualified_name)
        part.part_def_origin = rt.Reference(qualified_name=self._part_def, reference_type=rt.PartDef.__name__)
        part.attribute_redefinitions = [
            rt.AttributeRedefinition(
                name=attr_name,
                qualified_name=f"{self._qualified_name}::{attr_name}",
                redefined_feature=rt.Reference(qualified_name=declared[attr_name],
                                               reference_type=rt.AttributeUsageElement.__name__),
                value=value,
            )
            for attr_name, value in self._attribute_values.items()
        ]
        runtime.sysml.add_part_instantiation(part)


class AtomicUpdate(TranquilUpdate):
    """A list of tranquil updates applied as one (design doc, Topic 9
    "Atomic application of a list of updates"): at the same checkpoint, all
    or nothing. `condition()` is TranquilUpdate's, over the members' affected
    elements: the group waits until every part any member changes is
    tranquil.

    `apply()` checks every member before applying any, so a member that
    can't be applied leaves the runtime model unchanged. The simulation gets
    one batch for the whole group, since the observers record every member's
    change and the SynchronizationManager flushes once, at the next round
    start.

    Members are registry migrations: a member carrying an edit script is
    rejected, as is an empty list or a member that isn't a TranquilUpdate
    (it couldn't say what it affects).
    """

    def __init__(self, updates: list[TranquilUpdate], **kwargs) -> None:
        super().__init__(**kwargs)
        updates = list(updates)
        if not updates:
            raise ValueError("An AtomicUpdate needs at least one update.")
        for update in updates:
            if not isinstance(update, TranquilUpdate):
                raise ValueError(f"An AtomicUpdate's members must be TranquilUpdates, got {update!r}.")
            if update.edit_script is not None:
                raise ValueError(f"An AtomicUpdate's members can't carry an edit script ({update!r}).")
        self._updates = updates

    @property
    def updates(self) -> list[TranquilUpdate]:
        return list(self._updates)

    def affected_elements(self, runtime: RuntimeState) -> list[rt.TranquilityHolder]:
        """Every member's affected elements, each once, in member order."""
        elements = []
        for update in self._updates:
            for element in update.affected_elements(runtime):
                if not any(element is seen for seen in elements):
                    elements.append(element)
        return elements

    def check(self, runtime: RuntimeState) -> None:
        for update in self._updates:
            update.check(runtime)

    def apply(self, runtime: RuntimeState) -> None:
        self.check(runtime)
        for update in self._updates:
            update.apply(runtime)
