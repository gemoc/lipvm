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
    action_defs = [element for element in vm.state.elements if isinstance(element, rt.ActionDef)]
    assert len(action_defs) == 1

    print_def = action_defs[0]
    assert print_def.declared_name == "Print"
    assert print_def.qualified_name == "SimpleSimulationPackage::Print"
    assert [parameter.qualified_name for parameter in print_def.parameters] == ["msg"]
