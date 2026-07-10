from core.vm import *

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

    #Test if an action exist
    assert [reference.qualified_name for reference in action_defs_table.references] == ["SimpleSimulationPackage::Print"]

    print_def = action_defs_table.get_reference("SimpleSimulationPackage::Print").element_type
    assert isinstance(print_def, rt.ActionDef)
    assert print_def.declared_name == "Print"
    assert print_def.qualified_name == "SimpleSimulationPackage::Print"
    assert [parameter.declared_name for parameter in print_def.parameters] == ["msg"]
    assert [parameter.qualified_name for parameter in print_def.parameters] == ["SimpleSimulationPackage::Print::msg"]

    # msg is typed by the KerML library's ScalarValues::String, an
    # unresolved proxy in the loaded model, resolved via the local
    # kerml_libraries index rather than dereferencing the external resource.
    msg_type = print_def.parameters[0].type
    assert msg_type.kind == rt.TypeKind.SCALAR
    assert msg_type.scalar_type == rt.ScalarType.STRING
    assert msg_type.reference_type is None

    state_defs_table = sysml_state.lookup_table_state_defs

    # Test if a state exists
    assert [reference.qualified_name for reference in state_defs_table.references] == [
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

    item_defs_table = sysml_state.lookup_table_item_defs

    # Test if the items exist
    assert [reference.qualified_name for reference in item_defs_table.references] == [
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
