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
"""

from core.edit import Update
from core.language import RuntimeState

from languages.sysmlv2.syntax import StateUsage


def _executable_state_usages(runtime: RuntimeState):
    return [record.element_type
            for record in runtime.sysml.lookup_table_executable_state_usages.records]


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
