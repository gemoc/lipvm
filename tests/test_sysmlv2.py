from core.vm import *
from languages.sysmlv2.runtime import Parameter

from languages.sysmlv2.syntax import *
from languages.sysmlv2 import runtime as rt

from tools.load_xmi_with_syntax import load


def test_program_simple_machine():
    # Given
    resource = load("tests/test_sysmlv2-simple.xmi")
    root = resource.contents[0]

    scenario = Scenario(
        program_definition=root
    )

    # When
    vm = VirtualMachine()
    vm.scenario = scenario
    vm.init()
    vm.run()

    # Then
    sysml_state = vm.state.sysml
    assert isinstance(sysml_state, rt.SysmlRuntimeState)

    action_defs_table = sysml_state.lookup_table_action_defs

    #Test 1: If an action definition exist
    assert [reference.qualified_name for reference in action_defs_table.records] == ["SimpleSimulationPackage::Print"]

    print_def = action_defs_table.get_reference("SimpleSimulationPackage::Print").element_type
    assert isinstance(print_def, rt.ActionDef)
    assert print_def.declared_name == "Print"
    assert print_def.qualified_name == "SimpleSimulationPackage::Print"
    assert [parameter.declared_name for parameter in print_def.parameters] == ["msg"]
    assert [parameter.qualified_name for parameter in print_def.parameters] == ["SimpleSimulationPackage::Print::msg"]
    assert print_def.parameters[0].direction == rt.ParamDirection.IN

    # Print's formal `msg` parameter isn't bound to a default in the model
    # (only call sites like pIdle/pNext bind an actual value) — confirms
    # default_value stays None rather than picking up something spurious.
    assert print_def.parameters[0].default_value is None

    # Test 2: If a Parameter inside an action is discovered
    # msg is typed by the KerML library's ScalarValues::String, an
    # unresolved proxy in the loaded model, resolved via the local
    # kerml_libraries index rather than dereferencing the external resource.
    msg_type = print_def.parameters[0].type
    assert msg_type.kind == rt.TypeKind.SCALAR
    assert msg_type.scalar_type == rt.ScalarType.STRING
    assert msg_type.reference_type is None

    state_defs_table = sysml_state.lookup_table_state_defs

    # Test 3: if a state definition exists
    assert [reference.qualified_name for reference in state_defs_table.records] == [
        "SimpleSimulationPackage::MySimulationDefinition"
    ]

    simulation_def = state_defs_table.get_reference("SimpleSimulationPackage::MySimulationDefinition").element_type
    assert isinstance(simulation_def, rt.StateDef)
    assert simulation_def.declared_name == "MySimulationDefinition"
    assert simulation_def.qualified_name == "SimpleSimulationPackage::MySimulationDefinition"

    # MySimulationDefinition declares no formal (in/inout/out) parameters of
    # its own in the test model — only entry/transitions/substates — so
    # _populate_parameters() should leave this empty rather than error out.
    assert simulation_def.parameters == []

    # Test 4: If an entry action is discovered
    # entry_action is pEntry performing Print(msg="Entry"). action_def is a
    # bare Reference (qualified name only, like Parameter.type) — resolving
    # it against lookup_table_action_defs is left to whoever executes it.
    entry_action = simulation_def.entry_action
    assert isinstance(entry_action, rt.ActualAction)
    assert entry_action.action_def.qualified_name == "SimpleSimulationPackage::Print"
    assert entry_action.action_def.reference_type == rt.ActionDef.__name__
    assert [argument.declared_name for argument in entry_action.arguments] == ["msg"]
    assert entry_action.arguments[0].value.value == "Entry"

    # Test if a default transition is discovered
    # default_transition is the unconditional transition fired right after
    # entry finishes, straight into Idle — no source substate (it fires out
    # of the entry action, not a state) and no trigger/effect of its own.
    default_transition = simulation_def.default_transition
    assert isinstance(default_transition, rt.Transition)
    assert default_transition.source is None
    assert default_transition.trigger is None
    assert default_transition.effect is None
    assert default_transition.target.qualified_name == "SimpleSimulationPackage::MySimulationDefinition::Idle"

    # Idle/Next are MySimulationDefinition's own nested substates: purely
    # structural placeholders (rt.StateUsage), unlike the independently
    # running rt.ExecutableStateUsage checked below.
    assert [substate.declared_name for substate in simulation_def.substates] == ["Idle", "Next"]
    assert [substate.qualified_name for substate in simulation_def.substates] == [
        "SimpleSimulationPackage::MySimulationDefinition::Idle",
        "SimpleSimulationPackage::MySimulationDefinition::Next",
    ]
    assert all(isinstance(substate, rt.StateUsage) for substate in simulation_def.substates)

    # Each substate's contained_transitions holds the transition(s) firing
    # out of it (matched via the TransitionUsage's plain
    # Membership.memberElement) — Idle -[NextTrans]-> Next do pNext, and
    # Next -[IdleTrans]-> Idle do pIdle.
    idle, next_ = simulation_def.substates
    assert len(idle.contained_transitions) == 1
    idle_to_next = idle.contained_transitions[0]
    assert isinstance(idle_to_next, rt.Transition)
    assert idle_to_next.source.qualified_name == "SimpleSimulationPackage::MySimulationDefinition::Idle"
    assert idle_to_next.trigger is None
    assert idle_to_next.target.qualified_name == "SimpleSimulationPackage::MySimulationDefinition::Next"
    assert idle_to_next.effect.action_def.qualified_name == "SimpleSimulationPackage::Print"
    assert [argument.value.value for argument in idle_to_next.effect.arguments] == ["Hello World"]

    assert len(next_.contained_transitions) == 1
    next_to_idle = next_.contained_transitions[0]
    assert isinstance(next_to_idle, rt.Transition)
    assert next_to_idle.target.qualified_name == "SimpleSimulationPackage::MySimulationDefinition::Idle"
    assert next_to_idle.effect.action_def.qualified_name == "SimpleSimulationPackage::Print"
    assert [argument.value.value for argument in next_to_idle.effect.arguments] == ["Next Please"]

    state_usages_table = sysml_state.lookup_table_executable_state_usages

    # `main` is a StateUsage declared directly under the package (not nested
    # in any StateDefinition), explicitly typed by MySimulationDefinition —
    # the actual instance of the state machine, as opposed to Idle/Next above.
    assert [reference.qualified_name for reference in state_usages_table.records] == [
        "SimpleSimulationPackage::main"
    ]

    main_usage = state_usages_table.get_reference("SimpleSimulationPackage::main").element_type
    assert isinstance(main_usage, rt.ExecutableStateUsage)
    assert main_usage.declared_name == "main"
    assert main_usage.qualified_name == "SimpleSimulationPackage::main"

    # state_def_origin is a bare Reference carrying just the qualified name
    # (like Parameter.type/_build_type_ref) — it's never looked up against
    # lookup_table_state_defs at build time, so element_type stays
    # unresolved until whoever executes this usage dereferences it later.
    assert isinstance(main_usage.state_def_origin, rt.Reference)
    assert main_usage.state_def_origin.qualified_name == "SimpleSimulationPackage::MySimulationDefinition"
    assert main_usage.state_def_origin.reference_type == rt.StateDef.__name__

    item_defs_table = sysml_state.lookup_table_item_defs

    # Test if the items exist
    assert [reference.qualified_name for reference in item_defs_table.records] == [
        "SimpleSimulationPackage::IdleTrans",
        "SimpleSimulationPackage::NextTrans",
    ]

    idle_trans_def = item_defs_table.get_reference("SimpleSimulationPackage::IdleTrans").element_type
    assert isinstance(idle_trans_def, rt.ItemDef)
    assert idle_trans_def.declared_name == "IdleTrans"
    assert idle_trans_def.qualified_name == "SimpleSimulationPackage::IdleTrans"

    next_trans_def = item_defs_table.get_reference("SimpleSimulationPackage::NextTrans").element_type
    assert isinstance(next_trans_def, rt.ItemDef)
    assert next_trans_def.declared_name == "NextTrans"
    assert next_trans_def.qualified_name == "SimpleSimulationPackage::NextTrans"
