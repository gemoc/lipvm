from core.vm import *

from languages.sysmlv2.syntax import *

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
    