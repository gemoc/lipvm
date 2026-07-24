import pytest

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
    vm.step()

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
    assert entry_action.arguments[0].value.scalar_type == rt.ScalarType.STRING

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

    # pIdle is a direct reference (FeatureTyping straight to Print), not a
    # parameter-rooted feature chain (see ConveyorBeltNominalMission's
    # `do conveyorBelt.moveToSensor` in test_simple_conveyor_belt_simulation
    # for that shape) — target stays unset here.
    assert idle_to_next.effect.target is None

    assert len(next_.contained_transitions) == 1
    next_to_idle = next_.contained_transitions[0]
    assert isinstance(next_to_idle, rt.Transition)
    assert next_to_idle.source.qualified_name == "SimpleSimulationPackage::MySimulationDefinition::Next"
    assert isinstance(next_to_idle.trigger, rt.TransitionTriggerBySignal)
    assert next_to_idle.trigger.signal_origin.qualified_name == "SimpleSimulationPackage::NextTrans"
    assert next_to_idle.target.qualified_name == "SimpleSimulationPackage::MySimulationDefinition::Idle"

    next_to_idle_target_transition = simulation_def.get_substate(next_to_idle.target.qualified_name)
    assert next_to_idle_target_transition is not None
    assert simulation_def.get_substate(next_to_idle.target.qualified_name).qualified_name == "SimpleSimulationPackage::MySimulationDefinition::Idle"
    assert next_to_idle.effect.action_def.qualified_name == "SimpleSimulationPackage::Print"
    assert [argument.value.el for argument in next_to_idle.effect.arguments] == ["Next Please"]
    assert next_to_idle.effect.target is None

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
    vm.step()

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
    assert [attribute.name for attribute in factory_coordinate_def.contained_attribute_use] == ["x", "y", "degrees"]

    x_attribute, y_attribute, degrees_attribute = factory_coordinate_def.contained_attribute_use
    assert x_attribute.type.kind == rt.TypeKind.SCALAR
    assert x_attribute.type.scalar_type == rt.ScalarType.REAL
    assert x_attribute.type.reference_type is None

    assert y_attribute.type.kind == rt.TypeKind.SCALAR
    assert y_attribute.type.scalar_type == rt.ScalarType.REAL
    assert y_attribute.type.reference_type is None

    assert degrees_attribute.type.kind == rt.TypeKind.SCALAR
    assert degrees_attribute.type.scalar_type == rt.ScalarType.REAL
    assert degrees_attribute.type.reference_type is None

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

    # Test 11: Check cb1's attribute redefinition — `attribute :>>
    # placementCoordinate { attribute :>> x = 10.0; attribute :>> y = 0.0;
    # attribute :>> degrees = 0.0; }` (x/y/degrees are Real, not Integer).
    # placementCoordinate itself redefines ConveyorBeltMachine's attribute of
    # the same name, and its value is a CompositeCustomValue (rather than a
    # plain literal) since FactoryCoordinate is a composite/custom type —
    # x/y live inside it as named elements, not as separate top-level
    # redefinitions of their own.
    assert [redefinition.name for redefinition in cb1.attribute_redefinitions] == ["placementCoordinate"]

    placement_redefinition = cb1.attribute_redefinitions[0]
    assert isinstance(placement_redefinition, rt.AttributeRedefinition)
    assert placement_redefinition.qualified_name == "Main::cb1::placementCoordinate"
    assert placement_redefinition.redefined_feature.qualified_name == \
        "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine::placementCoordinate"
    assert placement_redefinition.redefined_feature.reference_type == rt.AttributeUsageElement.__name__

    placement_value = placement_redefinition.value
    assert isinstance(placement_value, rt.CompositeCustomValue)
    assert placement_value.type.kind == rt.TypeKind.CUSTOM
    assert placement_value.type.reference_type.qualified_name == "Common::FactoryCoordinate"
    assert placement_value.type.reference_type.reference_type == rt.CustomAttributeDefinition.__name__

    assert [element.name for element in placement_value.elements] == ["x", "y", "degrees"]
    assert [element.qualified_name for element in placement_value.elements] == [
        "Main::cb1::placementCoordinate::x", "Main::cb1::placementCoordinate::y", "Main::cb1::placementCoordinate::degrees"
    ]
    assert all(isinstance(element.value, rt.LiteralValue) for element in placement_value.elements)
    assert [element.value.el for element in placement_value.elements] == ["10.0", "0.0", "0.0"]

    # Test 12: Check ConveyorBeltNominalMission's formal parameter
    # (`in conveyorBelt : ConveyorBeltMachine`) — unlike MySimulationDefinition
    # (test_program_simple_machine), which declares no formal parameters at
    # all, this exercises _populate_parameters() actually appending one.
    state_defs_table = sysml_state.lookup_table_state_defs
    assert [reference.qualified_name for reference in state_defs_table.records] == [
        "ConveyorBeltStates::ConveyorBeltNominalMission"
    ]

    mission_def = state_defs_table.get_reference("ConveyorBeltStates::ConveyorBeltNominalMission").element_type
    assert isinstance(mission_def, rt.StateDef)
    assert mission_def.name == "ConveyorBeltNominalMission"
    assert mission_def.qualified_name == "ConveyorBeltStates::ConveyorBeltNominalMission"

    assert [parameter.name for parameter in mission_def.parameters] == ["conveyorBelt"]
    assert [parameter.qualified_name for parameter in mission_def.parameters] == [
        "ConveyorBeltStates::ConveyorBeltNominalMission::conveyorBelt"
    ]

    conveyor_belt_parameter = mission_def.parameters[0]
    assert conveyor_belt_parameter.direction == rt.ParamDirection.IN
    assert conveyor_belt_parameter.type.kind == rt.TypeKind.PART
    assert conveyor_belt_parameter.type.scalar_type == rt.ScalarType.NONE
    assert conveyor_belt_parameter.type.reference_type.qualified_name == \
           "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine"
    assert conveyor_belt_parameter.type.reference_type.reference_type == rt.PartDef.__name__
    assert conveyor_belt_parameter.default_value is None

    # Test 13: Check ConveyorBeltNominalMission's own nested substates
    # (Idle, MovingToSensor) — purely structural placeholders (rt.StateUsage),
    # same shape as MySimulationDefinition's Idle/Next in
    # test_program_simple_machine, just for a different state machine.
    assert [substate.name for substate in mission_def.substates] == ["Idle", "MovingToSensor"]
    assert [substate.qualified_name for substate in mission_def.substates] == [
        "ConveyorBeltStates::ConveyorBeltNominalMission::Idle",
        "ConveyorBeltStates::ConveyorBeltNominalMission::MovingToSensor",
    ]
    assert all(isinstance(substate, rt.StateUsage) for substate in mission_def.substates)

    # Test 14: Check the chained transition effects (`do conveyorBelt.
    # moveToSensor` / `do conveyorBelt.stop`) — unlike a direct effect (e.g.
    # pIdle performing Print in test_program_simple_machine), the
    # PerformActionUsage here has no FeatureTyping of its own; it's reached
    # via a parameter-rooted feature chain (ReferenceSubsetting +
    # FeatureChaining), so name/qualified_name/action_def come from the
    # chain's last hop (the PartDef-contained action actually being
    # invoked) rather than the anonymous PerformActionUsage itself, and
    # target records the chain's first hop (the formal parameter it's
    # invoked through) — both as bare, unresolved References.
    idle_substate, moving_substate = mission_def.substates
    assert len(idle_substate.contained_transitions) == 1
    idle_to_moving = idle_substate.contained_transitions[0]
    assert isinstance(idle_to_moving, rt.Transition)

    move_to_sensor_effect = idle_to_moving.effect
    assert isinstance(move_to_sensor_effect, rt.ActualAction)
    assert move_to_sensor_effect.name == "moveToSensor"
    assert move_to_sensor_effect.qualified_name == \
        "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine::moveToSensor"
    assert move_to_sensor_effect.target.qualified_name == \
        "ConveyorBeltStates::ConveyorBeltNominalMission::conveyorBelt"
    assert move_to_sensor_effect.target.reference_type == rt.Parameter.__name__
    assert move_to_sensor_effect.action_def.qualified_name == \
        "ConveyorBeltSystem::ConveyorBeltCommands::MoveToSensor"
    assert move_to_sensor_effect.action_def.reference_type == rt.ActionDef.__name__

    # `do conveyorBelt.moveToSensor { in direction = DirectionKind::FORWARD; }`
    # binds an argument directly at the transition-effect call site — the
    # same _bound_arguments(self) already used for the direct-reference
    # case (e.g. pIdle's msg="Entry") picks this up with no extra code,
    # since self (the chained PerformActionUsage) is still where a
    # call-site binding like this actually lives.
    assert [argument.name for argument in move_to_sensor_effect.arguments] == ["direction"]
    direction_argument = move_to_sensor_effect.arguments[0]
    assert isinstance(direction_argument.value, rt.ReferenceValue)
    assert direction_argument.value.el.qualified_name == \
        "ConveyorBeltSystem::ConveyorBeltCommands::DirectionKind::FORWARD"

    assert len(moving_substate.contained_transitions) == 1
    moving_to_idle = moving_substate.contained_transitions[0]
    assert isinstance(moving_to_idle, rt.Transition)

    stop_effect = moving_to_idle.effect
    assert isinstance(stop_effect, rt.ActualAction)
    assert stop_effect.name == "stop"
    assert stop_effect.qualified_name == "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine::stop"
    assert stop_effect.target.qualified_name == "ConveyorBeltStates::ConveyorBeltNominalMission::conveyorBelt"
    assert stop_effect.target.reference_type == rt.Parameter.__name__
    assert stop_effect.action_def.qualified_name == "ConveyorBeltSystem::ConveyorBeltCommands::Stop"
    assert stop_effect.action_def.reference_type == rt.ActionDef.__name__

    # Test 15: Check the transitions' own source/target substates — distinct
    # from ActualAction.target above (which parameter an effect is invoked
    # through), this is which substate a Transition fires from/into, same
    # shape as MySimulationDefinition's Idle/Next transitions in
    # test_program_simple_machine.
    assert idle_to_moving.source.qualified_name == "ConveyorBeltStates::ConveyorBeltNominalMission::Idle"
    assert idle_to_moving.target.qualified_name == "ConveyorBeltStates::ConveyorBeltNominalMission::MovingToSensor"

    assert moving_to_idle.source.qualified_name == "ConveyorBeltStates::ConveyorBeltNominalMission::MovingToSensor"
    assert moving_to_idle.target.qualified_name == "ConveyorBeltStates::ConveyorBeltNominalMission::Idle"

    # Test 16: Check ConveyorBeltNominalMission's own default_transition —
    # the unconditional transition fired right after entry finishes, same
    # shape as MySimulationDefinition's in test_program_simple_machine: no
    # source (it fires out of the entry action, not a state) and no
    # trigger/effect of its own, straight into Idle.
    mission_default_transition = mission_def.default_transition
    assert isinstance(mission_default_transition, rt.Transition)
    assert mission_default_transition.source is None
    assert mission_default_transition.trigger is None
    assert mission_default_transition.effect is None
    assert mission_default_transition.target.qualified_name == "ConveyorBeltStates::ConveyorBeltNominalMission::Idle"

    # Test 17: Check the `accept when` triggers — a boolean-expression
    # trigger (TransitionTriggerByWhenCondition), distinct from the plain
    # signal-typed trigger (TransitionTriggerBySignal) covered in
    # test_program_simple_machine. MovingToSensor's own trigger is the
    # simple case (`conveyorBelt.conveyorSensSwap == true`); Idle's is the
    # compound case (`conveyorBelt.conveyorSensFeed == true and
    # conveyorBelt.conveyorSensSwap == false`), which falls out of the same
    # recursive BinaryExpression shape with no extra machinery.
    idle_trigger = idle_to_moving.trigger
    assert isinstance(idle_trigger, rt.TransitionTriggerByWhenCondition)

    idle_condition = idle_trigger.condition
    assert isinstance(idle_condition, rt.BinaryExpression)
    assert idle_condition.operator == "and"

    def assert_attribute_comparison(comparison, attribute_name, expected_el, expected_scalar_type):
        assert isinstance(comparison, rt.BinaryExpression)
        assert comparison.operator == "=="
        assert isinstance(comparison.left, rt.AttributeReference)
        assert comparison.left.target.qualified_name == "ConveyorBeltStates::ConveyorBeltNominalMission::conveyorBelt"
        assert comparison.left.target.reference_type == rt.Parameter.__name__
        assert comparison.left.attribute.qualified_name == \
            f"ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine::{attribute_name}"
        assert comparison.left.attribute.reference_type == rt.AttributeUsageElement.__name__
        assert isinstance(comparison.right, rt.LiteralValue)
        assert comparison.right.el == expected_el
        assert comparison.right.scalar_type == expected_scalar_type

    assert_attribute_comparison(idle_condition.left, "conveyorSensFeed", "True", rt.ScalarType.BOOLEAN)
    assert_attribute_comparison(idle_condition.right, "conveyorSensSwap", "False", rt.ScalarType.BOOLEAN)

    moving_trigger = moving_to_idle.trigger
    assert isinstance(moving_trigger, rt.TransitionTriggerByWhenCondition)
    assert_attribute_comparison(moving_trigger.condition, "conveyorSensSwap", "True", rt.ScalarType.BOOLEAN)

def test_simple_sysmlv2_example_with_behaviour(capsys):
    # Given: the same simple simulation model as test_program_simple_machine —
    # MySimulationDefinition, entry pEntry performing Print(msg="Entry"),
    # default_transition into Idle, then Idle <-[IdleTrans/NextTrans]-> Next
    # with pNext/pIdle printing "Hello World"/"Next Please" as their effects.
    resource = load("tests/test_sysmlv2-simple.xmi")
    root = resource.contents[0]

    scenario = Scenario(
        program_definition=root
    )

    # When: the model is resolved — vm.run() only builds the registry now,
    # it doesn't hand off to any ExecutableStateUsage on its own.
    vm = VirtualMachine()
    vm.scenario = scenario
    vm.init()
    vm.step()

    sysml_state = vm.state.sysml
    main_usage = sysml_state.lookup_table_executable_state_usages.records[0].element_type
    assert main_usage.current is None

    vm.step()
    # Then: the entry action fired once, and the unconditional
    # default_transition moved `current` straight to Idle.
    assert main_usage.current is not None
    assert main_usage.current.qualified_name == "SimpleSimulationPackage::MySimulationDefinition::Idle"
    assert list(main_usage.pending) == []

    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["Entry"]

    # When: an IdleTrans signal arrives while in Idle.
    idle_trans = sysml_state.lookup_table_item_defs.get_reference("SimpleSimulationPackage::IdleTrans").element_type
    main_usage.pending.append(idle_trans)

    # Step 3
    vm.step()

    # Then: the Idle -> Next transition fires — runs its effect
    # (Print(msg="Hello World")), consumes the matched item from `pending`,
    # and moves `current` to Next.
    assert main_usage.current.qualified_name == "SimpleSimulationPackage::MySimulationDefinition::Next"
    assert list(main_usage.pending) == []

    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["Hello World"]

    # When: a NextTrans signal arrives while in Next.
    next_trans = sysml_state.lookup_table_item_defs.get_reference("SimpleSimulationPackage::NextTrans").element_type
    main_usage.pending.append(next_trans)

    # Step 4
    vm.step()

    # Then: the Next -> Idle transition fires (Print(msg="Next Please")),
    # completing one full Idle -> Next -> Idle cycle.
    assert main_usage.current.qualified_name == "SimpleSimulationPackage::MySimulationDefinition::Idle"
    assert list(main_usage.pending) == []

    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["Next Please"]

