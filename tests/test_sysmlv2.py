from core.vm import *
from languages.sysmlv2.runtime import Parameter, ElementDefinition

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
    assert print_def.name == "Print"
    assert print_def.qualified_name == "SimpleSimulationPackage::Print"
    assert [parameter.name for parameter in print_def.parameters] == ["msg"]
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
    assert simulation_def.name == "MySimulationDefinition"
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
    assert [argument.name for argument in entry_action.arguments] == ["msg"]
    assert entry_action.arguments[0].value.el == "Entry"

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
    assert [substate.name for substate in simulation_def.substates] == ["Idle", "Next"]
    assert [substate.qualified_name for substate in simulation_def.substates] == [
        "SimpleSimulationPackage::MySimulationDefinition::Idle",
        "SimpleSimulationPackage::MySimulationDefinition::Next",
    ]
    assert all(isinstance(substate, rt.StateUsage) for substate in simulation_def.substates)

    # Each substate's contained_transitions holds the transition(s) firing
    # out of it (matched via the TransitionUsage's plain
    # Membership.memberElement) — Idle -[IdleTrans]-> Next do pNext, and
    # Next -[NextTrans]-> Idle do pIdle.
    idle, next_ = simulation_def.substates
    assert len(idle.contained_transitions) == 1
    idle_to_next = idle.contained_transitions[0]
    assert isinstance(idle_to_next, rt.Transition)
    assert idle_to_next.source.qualified_name == "SimpleSimulationPackage::MySimulationDefinition::Idle"
    assert isinstance(idle_to_next.trigger, rt.TransitionTriggerBySignal)
    assert idle_to_next.trigger.signal_origin.qualified_name == "SimpleSimulationPackage::IdleTrans"
    assert idle_to_next.trigger.signal_origin.reference_type == rt.ItemDef.__name__
    assert idle_to_next.target.qualified_name == "SimpleSimulationPackage::MySimulationDefinition::Next"
    assert idle_to_next.effect.action_def.qualified_name == "SimpleSimulationPackage::Print"
    assert [argument.value.el for argument in idle_to_next.effect.arguments] == ["Hello World"]

    assert len(next_.contained_transitions) == 1
    next_to_idle = next_.contained_transitions[0]
    assert isinstance(next_to_idle, rt.Transition)
    assert isinstance(next_to_idle.trigger, rt.TransitionTriggerBySignal)
    assert next_to_idle.trigger.signal_origin.qualified_name == "SimpleSimulationPackage::NextTrans"
    assert next_to_idle.target.qualified_name == "SimpleSimulationPackage::MySimulationDefinition::Idle"

    next_to_idle_target_transition = simulation_def.get_substate(next_to_idle.target.qualified_name)
    assert next_to_idle_target_transition is not None
    assert simulation_def.get_substate(next_to_idle.target.qualified_name).qualified_name == "SimpleSimulationPackage::MySimulationDefinition::Idle"
    assert next_to_idle.effect.action_def.qualified_name == "SimpleSimulationPackage::Print"
    assert [argument.value.el for argument in next_to_idle.effect.arguments] == ["Next Please"]

    state_usages_table = sysml_state.lookup_table_executable_state_usages

    # `main` is a StateUsage declared directly under the package (not nested
    # in any StateDefinition), explicitly typed by MySimulationDefinition —
    # the actual instance of the state machine, as opposed to Idle/Next above.
    assert [reference.qualified_name for reference in state_usages_table.records] == [
        "SimpleSimulationPackage::main"
    ]

    main_usage = state_usages_table.get_reference("SimpleSimulationPackage::main").element_type
    assert isinstance(main_usage, rt.ExecutableStateUsage)
    assert main_usage.name == "main"
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
    assert idle_trans_def.name == "IdleTrans"
    assert idle_trans_def.qualified_name == "SimpleSimulationPackage::IdleTrans"

    next_trans_def = item_defs_table.get_reference("SimpleSimulationPackage::NextTrans").element_type
    assert isinstance(next_trans_def, rt.ItemDef)
    assert next_trans_def.name == "NextTrans"
    assert next_trans_def.qualified_name == "SimpleSimulationPackage::NextTrans"

def test_simple_conveyor_belt_simulation():
    # Given
    resource = load("tests/conveyor-belt-simulation.xmi")
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

    # Test 1: If an action definition exist
    assert ([reference.qualified_name for reference in action_defs_table.records] ==
            ["ConveyorBeltSystem::ConveyorBeltCommands::MoveToSensor", "ConveyorBeltSystem::ConveyorBeltCommands::MoveOut",
             "ConveyorBeltSystem::ConveyorBeltCommands::MoveNbSteps", "ConveyorBeltSystem::ConveyorBeltCommands::Stop",
             "ConveyorBeltSystem::ConveyorBeltCommands::StatusRequest"])

    #Test 2: Get one action definition with parameter and without parameter.
    move_nb_steps_def = action_defs_table.get_reference("ConveyorBeltSystem::ConveyorBeltCommands::MoveNbSteps").element_type
    assert isinstance(move_nb_steps_def, rt.ActionDef)
    assert [parameter.name for parameter in move_nb_steps_def.parameters] == ["steps", "direction"]
    assert move_nb_steps_def.parameters[0].type.kind == rt.TypeKind.SCALAR
    assert move_nb_steps_def.parameters[0].type.scalar_type == rt.ScalarType.INTEGER
    assert move_nb_steps_def.parameters[1].type.kind == rt.TypeKind.ENUM
    assert move_nb_steps_def.parameters[1].type.reference_type.qualified_name == "ConveyorBeltSystem::ConveyorBeltCommands::DirectionKind"

    stop_def = action_defs_table.get_reference("ConveyorBeltSystem::ConveyorBeltCommands::Stop").element_type
    assert isinstance(stop_def, rt.ActionDef)
    assert list(stop_def.parameters) == []

    #Test 3: Checking enumeration definition
    enumeration_defs_table = sysml_state.lookup_table_enum_defs

    assert ([reference.qualified_name for reference in enumeration_defs_table.records] ==
            ["ConveyorBeltSystem::ConveyorBeltCommands::ConveyorCommandKind",
             "ConveyorBeltSystem::ConveyorBeltCommands::DirectionKind"])

    conveyor_command_kind_def = enumeration_defs_table.get_reference(
        "ConveyorBeltSystem::ConveyorBeltCommands::ConveyorCommandKind").element_type
    assert isinstance(conveyor_command_kind_def, rt.EnumerationDefinition)
    assert list(conveyor_command_kind_def.contained_values) == [
        "MOVE_TO_SENSOR", "MOVE_OUT", "MOVE_NB_STEPS", "STOP", "STATUS_REQUEST"
    ]

    direction_kind_def = enumeration_defs_table.get_reference(
        "ConveyorBeltSystem::ConveyorBeltCommands::DirectionKind").element_type
    assert isinstance(direction_kind_def, rt.EnumerationDefinition)
    assert list(direction_kind_def.contained_values) == ["FORWARD", "BACKWARD"]

    # Test 4: Checking custom attribute definition
    custom_attribute_definition = sysml_state.lookup_table_attribute_defs
    assert [reference.qualified_name for reference in custom_attribute_definition.records] == ["Common::FactoryCoordinate"]

    factory_coordinate_def = custom_attribute_definition.get_reference("Common::FactoryCoordinate").element_type
    assert isinstance(factory_coordinate_def, rt.CustomAttributeDefinition)
    assert [attribute.name for attribute in factory_coordinate_def.contained_attribute_use] == ["x", "y"]

    x_attribute, y_attribute = factory_coordinate_def.contained_attribute_use
    assert x_attribute.type.kind == rt.TypeKind.SCALAR
    assert x_attribute.type.scalar_type == rt.ScalarType.REAL
    assert x_attribute.type.reference_type is None

    assert y_attribute.type.kind == rt.TypeKind.SCALAR
    assert y_attribute.type.scalar_type == rt.ScalarType.REAL
    assert y_attribute.type.reference_type is None

    # Test 5: Checking part definition
    part_definition = sysml_state.lookup_table_part_defs
    assert [reference.qualified_name for reference in part_definition.records] == ["Common::Machine",
                                               "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine"]

    machine_def = part_definition.get_reference("Common::Machine").element_type
    assert isinstance(machine_def, rt.PartDef)
    assert list(machine_def.attributes) == []

    conveyor_belt_machine_def = part_definition.get_reference(
        "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine").element_type
    assert isinstance(conveyor_belt_machine_def, rt.PartDef)
    assert [attribute.name for attribute in conveyor_belt_machine_def.attributes] == [
        "currentCommand", "direction", "currentStepCount", "targetStepCount",
        "conveyorSensFeed", "conveyorSensSwap", "conveyorSensImpulse", "placementCoordinate",
    ]

    #Checking the internal structure of the attributes
    current_command_attribute = conveyor_belt_machine_def.attributes[0]
    assert current_command_attribute.type.kind == rt.TypeKind.ENUM
    assert current_command_attribute.type.scalar_type == rt.ScalarType.NONE
    assert current_command_attribute.type.reference_type.qualified_name == "ConveyorBeltSystem::ConveyorBeltCommands::ConveyorCommandKind"
    assert current_command_attribute.default_value == None

    conveyor_sens_feed_attribute = conveyor_belt_machine_def.attributes[4]
    assert conveyor_sens_feed_attribute.type.kind == rt.TypeKind.SCALAR
    assert conveyor_sens_feed_attribute.type.scalar_type == rt.ScalarType.BOOLEAN
    assert conveyor_sens_feed_attribute.type.reference_type is None
    assert conveyor_sens_feed_attribute.default_value == None

    placement_coordinate_attribute = conveyor_belt_machine_def.attributes[-1]
    assert placement_coordinate_attribute.type.kind == rt.TypeKind.CUSTOM
    assert placement_coordinate_attribute.type.scalar_type == rt.ScalarType.NONE
    assert placement_coordinate_attribute.type.reference_type.qualified_name == "Common::FactoryCoordinate"
    assert placement_coordinate_attribute.type.reference_type.reference_type == rt.CustomAttributeDefinition.__name__
    assert placement_coordinate_attribute.default_value == None

    # Test 6: Checking performed actions inside part definition
    assert [perform_action.name for perform_action in conveyor_belt_machine_def.contained_perform_actions] == [
        "moveToSensor", "moveOut", "moveNbSteps", "stop", "statusRequest",
    ]
    assert [perform_action.qualified_name for perform_action in conveyor_belt_machine_def.contained_perform_actions] == [
        "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine::moveToSensor",
        "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine::moveOut",
        "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine::moveNbSteps",
        "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine::stop",
        "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine::statusRequest",
    ]
    assert [perform_action.action_def.qualified_name for perform_action in conveyor_belt_machine_def.contained_perform_actions] == [
        "ConveyorBeltSystem::ConveyorBeltCommands::MoveToSensor",
        "ConveyorBeltSystem::ConveyorBeltCommands::MoveOut",
        "ConveyorBeltSystem::ConveyorBeltCommands::MoveNbSteps",
        "ConveyorBeltSystem::ConveyorBeltCommands::Stop",
        "ConveyorBeltSystem::ConveyorBeltCommands::StatusRequest",
    ]
    assert all(isinstance(perform_action, rt.ActualAction) for perform_action in conveyor_belt_machine_def.contained_perform_actions)
    assert all(perform_action.action_def.reference_type == rt.ActionDef.__name__
               for perform_action in conveyor_belt_machine_def.contained_perform_actions)
    assert all(list(perform_action.arguments) == [] for perform_action in conveyor_belt_machine_def.contained_perform_actions)

    # Test 7: Check Item definition as messages/event that can be sent or received
    item_definition = sysml_state.lookup_table_item_defs

    assert [reference.qualified_name for reference in item_definition.records] == ["Common::Messages::EventMessage",
        "ConveyorBeltSystem::ConveyorBeltMessages::FeedFreeEventMessage",
        "ConveyorBeltSystem::ConveyorBeltMessages::SwapBusyEventMessage",
        "ConveyorBeltSystem::ConveyorBeltMessages::CBCommandSuccessEventMessage"]

    # Test 8: Check executable states
    executable_states = sysml_state.lookup_table_executable_state_usages

    assert [reference.qualified_name for reference in executable_states.records] == ["Main::cbSimulation"]

    cb_simulation = executable_states.records[0].element_type
    assert cb_simulation.state_def_origin.qualified_name == "ConveyorBeltStates::ConveyorBeltNominalMission"
    assert cb_simulation.state_def_origin.reference_type == rt.StateDef.__name__

    # Test 9: Check the executable state's bound in-parameters (conveyorBelt=cb1) —
    # captured as a ReferenceValue wrapping a bare Reference to the bound
    # feature (cb1), resolved through the FeatureReferenceExpression at
    # build time rather than left pointing at the raw AST node.
    assert [argument.name for argument in cb_simulation.arguments] == ["conveyorBelt"]
    assert [argument.qualified_name for argument in cb_simulation.arguments] == ["Main::cbSimulation::conveyorBelt"]

    conveyor_belt_argument = cb_simulation.arguments[0]
    assert isinstance(conveyor_belt_argument.value, rt.ReferenceValue)

    bound_reference = conveyor_belt_argument.value.el
    assert isinstance(bound_reference, rt.Reference)
    assert bound_reference.qualified_name == "Main::cb1"
    assert bound_reference.reference_type == "PartInstantiation"

    # Test 10: Check cb1 itself is registered as a PartInstantiation — the
    # actual part instance a PartUsage declared directly under a package
    # (not nested in any PartDefinition) becomes, as opposed to PartDef
    # (ConveyorBeltMachine, the shared blueprint it's typed by).
    part_instantiations = sysml_state.lookup_table_part_instantiations
    assert [reference.qualified_name for reference in part_instantiations.records] == ["Main::cb1"]

    cb1 = part_instantiations.records[0].element_type
    assert isinstance(cb1, rt.PartInstantiation)
    assert cb1.name == "cb1"
    assert cb1.qualified_name == "Main::cb1"
    assert cb1.part_def_origin.qualified_name == "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine"
    assert cb1.part_def_origin.reference_type == rt.PartDef.__name__


