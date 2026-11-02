"""Step 1 of the tranquility work (Language-Safe-and-Execution-Tranquility-points.md,
Topic 8): the interpreter recognises constraints labelled `#Tranquility`
(LiveModeling::Tranquility) in complete-interesting-simulation.

Written ahead of the implementation. `syntax._is_tranquility_constraint` is
looked up on the module inside the test, not imported at the top, so that
until it exists that test fails on its own rather than the whole module
failing to collect.
"""

import types

import pytest

from core.language import Scenario
from core.vm import ProgramUpdateOption, VirtualMachine

from languages.sysmlv2 import runtime as rt
from languages.sysmlv2 import syntax
from languages.sysmlv2 import updates
from languages.sysmlv2.runtime_utility import ScalarType, TypeKind
from languages.sysmlv2.simulation_models import synchronization
from languages.sysmlv2.simulation_models.fischertechnik.enums import ConveyorCommandKind
from languages.sysmlv2.syntax import AssertConstraintUsage, ConstraintUsage
from languages.sysmlv2.sysml_utility_classes import qualified_name

from tools.load_xmi_with_syntax import load


XMI = "tests/complete-interesting-simulation.xmi"


# --- Helpers ---

def _build(root=None) -> VirtualMachine:
    """Load the model (or use the already loaded `root`) and run the build/registry pass."""
    vm = VirtualMachine()
    vm.scenario = Scenario(program_definition=root if root is not None else load(XMI).contents[0])
    vm.init()
    vm.step()
    return vm


def _owner(constraint) -> str:
    """Qualified name of the element owning `constraint` (through its FeatureMembership)."""
    return qualified_name(constraint.eContainer().eContainer())


def _part_def(vm: VirtualMachine, part_def_qualified_name: str):
    """The registry's rt.PartDef for `part_def_qualified_name`."""
    return vm.state.sysml.lookup_table_part_defs.get_reference(part_def_qualified_name).element_type


# --- Tests ---

def test_part_defs_with_tranquility_constraints_are_still_registered():
    vm = _build()
    part_defs = [record.qualified_name for record in vm.state.sysml.lookup_table_part_defs.records]
    assert "TokenProducerSystem::TokenProducer::TokenProducerMachine" in part_defs
    assert "TokenDepoSystem::TokenDepo::TokenDepoMachine" in part_defs
    assert "VacuumGripperSystem::VacuumGripper::VacuumGripperMachine" in part_defs
    assert "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine" in part_defs


def test_tranquility_metadata_definition_is_not_registered_as_item_def():
    vm = _build()
    item_defs = [record.qualified_name for record in vm.state.sysml.lookup_table_item_defs.records]
    assert "LiveModeling::Tranquility" not in item_defs


def test_recognises_the_four_part_def_tranquility_constraints():
    root = load(XMI).contents[0]
    tranquility = [element for element in root.eAllContents()
                   if isinstance(element, ConstraintUsage) and syntax._is_tranquility_constraint(element)]
    assert sorted(_owner(constraint) for constraint in tranquility) == [
        "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine",
        "TokenDepoSystem::TokenDepo::TokenDepoMachine",
        "TokenProducerSystem::TokenProducer::TokenProducerMachine",
        "VacuumGripperSystem::VacuumGripper::VacuumGripperMachine",
    ]


# --- Step 2: tranquility conditions in the runtime registry ---

def _assert_comparison(condition, attribute_qualified_name: str, operator: str, literal: str) -> None:
    """`condition` is `<attribute> <operator> <literal>`, e.g. `platformSens == false`."""
    assert isinstance(condition, rt.BinaryExpression)
    assert condition.operator == operator
    assert isinstance(condition.left, rt.ReferenceValue)
    assert condition.left.el.qualified_name == attribute_qualified_name
    assert isinstance(condition.right, rt.LiteralValue)
    assert condition.right.el == literal


def _assert_enum_comparison(condition, attribute_qualified_name: str, operator: str,
                            enum_literal_qualified_name: str) -> None:
    """`condition` is `<attribute> <operator> <enum literal>`, e.g.
    `currentCommand == ConveyorCommandKind::STOP`: an enum literal is a
    reference to the enum member, not a LiteralValue."""
    assert isinstance(condition, rt.BinaryExpression)
    assert condition.operator == operator
    assert isinstance(condition.left, rt.ReferenceValue)
    assert condition.left.el.qualified_name == attribute_qualified_name
    assert isinstance(condition.right, rt.ReferenceValue)
    assert condition.right.el.reference_type == "EnumerationUsage"
    assert condition.right.el.qualified_name == enum_literal_qualified_name


def _conjuncts(condition) -> list:
    """Flattens a chain of `and`s into its operands, left to right."""
    if isinstance(condition, rt.BinaryExpression) and condition.operator == "and":
        return _conjuncts(condition.left) + _conjuncts(condition.right)
    return [condition]


def test_part_defs_carry_their_tranquility_condition():
    vm = _build()

    # `#Tranquility constraint { platformSens == false }`
    producer = "TokenProducerSystem::TokenProducer::TokenProducerMachine"
    [condition] = _part_def(vm, producer).tranquility_conditions
    _assert_comparison(condition, f"{producer}::platformSens", "==", "False")

    # `#Tranquility constraint { receiverSens == false }`
    depo = "TokenDepoSystem::TokenDepo::TokenDepoMachine"
    [condition] = _part_def(vm, depo).tranquility_conditions
    _assert_comparison(condition, f"{depo}::receiverSens", "==", "False")

    # `#Tranquility constraint { verticalEncoder == 0.0 and armEncoder == 0.0 and
    #   rotEncoder == 0.0 and vacuumActCompressorOn == false and vacuumActValve == false }`
    vgr = "VacuumGripperSystem::VacuumGripper::VacuumGripperMachine"
    [condition] = _part_def(vm, vgr).tranquility_conditions
    comparisons = _conjuncts(condition)
    assert len(comparisons) == 5
    _assert_comparison(comparisons[0], f"{vgr}::verticalEncoder", "==", "0.0")
    _assert_comparison(comparisons[1], f"{vgr}::armEncoder", "==", "0.0")
    _assert_comparison(comparisons[2], f"{vgr}::rotEncoder", "==", "0.0")
    _assert_comparison(comparisons[3], f"{vgr}::vacuumActCompressorOn", "==", "False")
    _assert_comparison(comparisons[4], f"{vgr}::vacuumActValve", "==", "False")

    # `#Tranquility constraint { currentCommand == ConveyorCommandKind::STOP }`
    cb = "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine"
    [condition] = _part_def(vm, cb).tranquility_conditions
    _assert_enum_comparison(condition, f"{cb}::currentCommand", "==",
                            "ConveyorBeltSystem::ConveyorBeltCommands::ConveyorCommandKind::STOP")


def test_part_def_without_tranquility_constraint_has_no_condition():
    # `part def Machine;`, the abstract base of every machine.
    part_def = _part_def(_build(), "Common::Machine")
    assert list(part_def.tranquility_conditions) == []


def test_asserted_tranquility_constraint_is_ignored():
    # Tranquility must not be an invariant (Topic 6), so the interpreter only
    # picks up unasserted constraints. `#Tranquility assert constraint` passes
    # the export, but is ignored like any other unsupported use of the label.
    root = load(XMI).contents[0]
    depo = "TokenDepoSystem::TokenDepo::TokenDepoMachine"
    [constraint] = [element for element in root.eAllContents()
                    if isinstance(element, ConstraintUsage) and _owner(element) == depo]

    # Turn `#Tranquility constraint { receiverSens == false }` into
    # `#Tranquility assert constraint { receiverSens == false }`: same label and
    # expression, moved onto an AssertConstraintUsage in the constraint's place.
    asserted = AssertConstraintUsage()
    asserted.ownedRelationship.extend(list(constraint.ownedRelationship))
    membership = constraint.eContainer()
    membership.ownedRelatedElement.remove(constraint)
    membership.ownedRelatedElement.append(asserted)

    assert list(_part_def(_build(root), depo).tranquility_conditions) == []


# --- Step 3: evaluating tranquility for a part instance ---

TOKEN_DEPO = "Main::tokenDepo"
VGR = "Main::vgrPickProducer"
CB_FEEDER = "Main::cbFeeder"


def _token_depo_values(**overrides) -> types.SimpleNamespace:
    """A complete simulation-side value object for a TokenDepoMachine: every
    attribute the part def declares in SysML."""
    values = dict(tokenCount=0, receiverSens=False, currentCommand=None, placementCoordinate=None)
    values.update(overrides)
    return types.SimpleNamespace(**values)


def _vgr_values(**overrides) -> types.SimpleNamespace:
    """A complete simulation-side value object for a VacuumGripperMachine,
    at home with the vacuum off unless overridden."""
    values = dict(currentCommand=None, executionStatus=None,
                  verticalEncoder=0.0, armEncoder=0.0, rotEncoder=0.0,
                  expectedVerticalEncoderValue=0.0, expectedArmEncoderValue=0.0,
                  expectedRotationEncoderValue=0.0,
                  vacuumActCompressorOn=False, vacuumActValve=False, placementCoordinate=None)
    values.update(overrides)
    return types.SimpleNamespace(**values)


def _conveyor_belt_values(**overrides) -> types.SimpleNamespace:
    """A complete simulation-side value object for a ConveyorBeltMachine,
    stopped unless overridden."""
    values = dict(currentCommand=ConveyorCommandKind.STOP, direction=None,
                  currentStepCount=0, targetStepCount=0,
                  conveyorSensFeed=False, conveyorSensSwap=False, conveyorSensImpulse=0,
                  placementCoordinate=None)
    values.update(overrides)
    return types.SimpleNamespace(**values)


def _publish_and_refresh(vm: VirtualMachine, snapshot: dict) -> None:
    """Stand in for the simulation publishing `snapshot`, then refresh the
    part instantiations' observed values from it."""
    vm.state.channel.latest_snapshot.publish(snapshot)
    syntax.refresh_part_values(
        vm.state.channel,
        vm.state.sysml.lookup_table_part_defs,
        syntax.get_part_instantiations(vm.state.sysml.lookup_table_part_instantiations))


def _is_tranquil(vm: VirtualMachine, part_usage: str) -> bool:
    """Asks the part instance whether it is tranquil now: it adopts its part
    def's tranquility conditions and evaluates them against itself."""
    part = vm.state.sysml.lookup_table_part_instantiations.get_reference(part_usage).element_type
    return part.is_tranquil(vm.state)


def test_token_depo_is_tranquil_when_no_token_at_receiver():
    vm = _build()
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=False)})
    assert _is_tranquil(vm, TOKEN_DEPO) is True
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=True)})
    assert _is_tranquil(vm, TOKEN_DEPO) is False


def test_evaluation_leaves_no_current_part_behind():
    # The part is only the evaluation context for the duration of the check.
    vm = _build()
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values()})
    _is_tranquil(vm, TOKEN_DEPO)
    assert vm.state.execution_context.current_part is None


def test_vgr_is_tranquil_only_at_home_with_vacuum_off():
    vm = _build()
    _publish_and_refresh(vm, {VGR: _vgr_values()})
    assert _is_tranquil(vm, VGR) is True
    _publish_and_refresh(vm, {VGR: _vgr_values(armEncoder=31.5)})
    assert _is_tranquil(vm, VGR) is False
    _publish_and_refresh(vm, {VGR: _vgr_values(vacuumActValve=True)})
    assert _is_tranquil(vm, VGR) is False


def test_conveyor_belt_is_tranquil_only_when_stopped():
    vm = _build()
    _publish_and_refresh(vm, {CB_FEEDER: _conveyor_belt_values()})
    assert _is_tranquil(vm, CB_FEEDER) is True
    _publish_and_refresh(vm, {CB_FEEDER: _conveyor_belt_values(currentCommand=ConveyorCommandKind.MOVE_TO_SENSOR)})
    assert _is_tranquil(vm, CB_FEEDER) is False


def test_part_missing_from_snapshot_is_not_tranquil():
    # Startup: the simulation hasn't created the part yet, so it has no
    # observed values and tranquility can't be confirmed.
    vm = _build()
    _publish_and_refresh(vm, {})
    assert _is_tranquil(vm, TOKEN_DEPO) is False


def test_part_def_without_tranquility_conditions_is_always_tranquil():
    # Step-4 decision: no #Tranquility constraint means the modeller accepts
    # possible inconsistency, so the part is always tranquil.
    # Every part def in the model has conditions, so remove ConveyorBeltMachine's
    # from the registry: cbFeeder is then typed by a part def without any, and
    # is tranquil even while moving.
    vm = _build()
    _part_def(vm, "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine").tranquility_conditions.clear()
    _publish_and_refresh(vm, {CB_FEEDER: _conveyor_belt_values(currentCommand=ConveyorCommandKind.MOVE_TO_SENSOR)})
    assert _is_tranquil(vm, CB_FEEDER) is True


def test_part_usage_carries_its_own_tranquility_condition():
    # A part adopts its part def's conditions plus its own (Topic 8). Move
    # `#Tranquility constraint { receiverSens == false }` from TokenDepoMachine
    # onto the part usage `tokenDepo`: the part now carries it itself.
    root = load(XMI).contents[0]
    depo = "TokenDepoSystem::TokenDepo::TokenDepoMachine"
    [constraint] = [element for element in root.eAllContents()
                    if isinstance(element, ConstraintUsage) and _owner(element) == depo]
    [token_depo_usage] = [element for element in root.eAllContents()
                          if isinstance(element, syntax.PartUsage) and qualified_name(element) == TOKEN_DEPO]
    membership = constraint.eContainer()
    membership.eContainer().ownedRelationship.remove(membership)
    token_depo_usage.ownedRelationship.append(membership)

    vm = _build(root)
    assert list(_part_def(vm, depo).tranquility_conditions) == []
    token_depo = vm.state.sysml.lookup_table_part_instantiations.get_reference(TOKEN_DEPO).element_type
    assert len(token_depo.tranquility_conditions) == 1

    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=False)})
    assert _is_tranquil(vm, TOKEN_DEPO) is True
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=True)})
    assert _is_tranquil(vm, TOKEN_DEPO) is False


# --- Step 4: tranquility-gated updates ---
# Written ahead of the implementation. `updates.ChangeRuntimeAttributeValue`
# is looked up on the module inside each test, so that until it exists each
# test fails on its own rather than the whole module failing to collect.

def _factory_coordinate(x: float, y: float, degrees: float) -> rt.CompositeCustomValue:
    """A registry value for `placementCoordinate`, shaped like the ones the
    build pass makes from `attribute :>> placementCoordinate { ... }`."""
    return rt.CompositeCustomValue(
        type=rt.TypeRef(kind=TypeKind.CUSTOM, reference_type=rt.Reference(
            qualified_name="Common::FactoryCoordinate", reference_type="CustomAttributeDefinition")),
        elements=[rt.Argument(name=name, value=rt.LiteralValue(el=str(value), scalar_type=ScalarType.REAL))
                  for name, value in (("x", x), ("y", y), ("degrees", degrees))])


def test_change_runtime_attribute_value_waits_until_the_part_is_tranquil():
    # Valentin's pattern (tests/test_sysmlv2_updates.py), with `submit`: hand
    # the update to the VM without running it, step to the StateUsage
    # before-checkpoint, and check whether it is still pending. The condition here is tokenDepo's
    # tranquility (`receiverSens == false`) instead of quiescence.
    vm = _build()
    update = updates.ChangeRuntimeAttributeValue(
        owner=TOKEN_DEPO, attribute="placementCoordinate",
        new_value=_factory_coordinate(x=25.0, y=35.0, degrees=270.0))
    vm.submit(update, ProgramUpdateOption.HOTSWAP)

    # A token at the receiver: not tranquil, so the update is held back.
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=True)})
    vm.step()
    assert vm.has_pending_update()

    # The receiver is free: tranquil, so the update is applied at the next
    # checkpoint.
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=False)})
    vm.step()
    assert not vm.has_pending_update()


def _placement_coordinate(vm: VirtualMachine, part_usage: str) -> dict:
    """The part usage's `placementCoordinate` redefinition in the registry, as
    {sub-attribute name: literal}."""
    part = vm.state.sysml.lookup_table_part_instantiations.get_reference(part_usage).element_type
    [redefinition] = [r for r in part.attribute_redefinitions if r.name == "placementCoordinate"]
    return {argument.name: argument.value.el for argument in redefinition.value.elements}


def test_change_runtime_attribute_value_replaces_the_redefinition_value():
    # VM side of the update: once applied, tokenDepo's
    # `attribute :>> placementCoordinate { x = 20.0; ... }` holds the new values.
    vm = _build()
    assert _placement_coordinate(vm, TOKEN_DEPO) == {"x": "20.0", "y": "35.0", "degrees": "270.0"}

    # Imagine if the token depo still hold a token
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=True)})
    vm.step()

    # Then comes the update
    vm.submit(updates.ChangeRuntimeAttributeValue(
        owner=TOKEN_DEPO, attribute="placementCoordinate",
        new_value=_factory_coordinate(x=25.0, y=30.0, degrees=180.0)), ProgramUpdateOption.HOTSWAP)
    vm.step()

    # At this point, the update should still exist
    assert vm.has_pending_update()
    assert _placement_coordinate(vm, TOKEN_DEPO) == {"x": "20.0", "y": "35.0", "degrees": "270.0"}

    # Then, assume the token held token depo now is picked up by the gripper
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=False)})
    vm.step()

    # At this point now, the update should be applied
    assert not vm.has_pending_update()
    assert _placement_coordinate(vm, TOKEN_DEPO) == {"x": "25.0", "y": "30.0", "degrees": "180.0"}


def _drain(q) -> list:
    """Everything currently in a channel queue, in order."""
    items = []
    while not q.empty():
        items.append(q.get_nowait())
    return items


def _step_round(vm: VirtualMachine) -> None:
    """Step every state machine once, so the round ends and the next one
    starts (where the SynchronizationManager flushes its batch)."""
    for _ in syntax.get_executable_state_usages(vm.state.sysml.lookup_table_executable_state_usages):
        vm.step()


def test_applied_update_sends_one_batch_with_the_changed_configured_values():
    # Runtime model -> simulation (design doc, Topic 10, "Syncing a runtime
    # change to the simulation"): pyecore notifications record which parts'
    # configured values changed during the update, and the bridge sends them as
    # one batch at the start of the next round. Observed values are refreshed
    # for several parts first: they must not end up in the batch.
    vm = _build()
    _publish_and_refresh(vm, {
        TOKEN_DEPO: _token_depo_values(receiverSens=False),
        CB_FEEDER: _conveyor_belt_values(),
        VGR: _vgr_values(),
    })
    vm.submit(updates.ChangeRuntimeAttributeValue(
        owner=TOKEN_DEPO, attribute="placementCoordinate",
        new_value=_factory_coordinate(x=25.0, y=30.0, degrees=180.0)), ProgramUpdateOption.HOTSWAP)
    _step_round(vm)
    assert not vm.has_pending_update()

    [batch] = _drain(vm.state.channel.model_update_queue)
    # Only tokenDepo: the others' observed values changed, but they aren't
    # sent back to the simulation.
    assert batch == [
        synchronization.SetAttributeCommand(TOKEN_DEPO, {
            "placementCoordinate": ("FactoryCoordinate", {"x": 25.0, "y": 30.0, "degrees": 180.0}),
        }),
    ]


def test_update_arriving_mid_round_waits_for_values_copied_while_paused():
    # Lockstep (design doc, Topic 10, "the mid-round gap"): the round that
    # starts while an update is pending waits for the simulation's question,
    # so its values are copied while the simulation is paused. An update that
    # arrives mid-round finds the round's values copied while the simulation
    # was still moving: tranquil or not, they may be stale, so it waits for
    # the next round.
    #
    # One vm.step() is one state machine: a checkpoint, then the machine. A
    # round starts at the end of the step that runs the previous round's last
    # machine (round 1: in the first step), so the first checkpoint after a
    # round start is the one before its machine 1.
    vm = _build()  # round 1 has started, no machine has run yet
    vm.state.channel.lockstep_enabled = True
    _publish_and_refresh(vm, {
        TOKEN_DEPO: _token_depo_values(receiverSens=False),
        CB_FEEDER: _conveyor_belt_values(),
        VGR: _vgr_values(),
    })
    machines = len(syntax.get_executable_state_usages(vm.state.sysml.lookup_table_executable_state_usages))

    _step_round(vm)  # round 1, machines 1 to 7; then round 2 starts (no update
                     # pending: copied while moving)
    vm.step()        # round 2, machine 1
    vm.step()        # round 2, machine 2

    # Mid-round 2, machines 3 to 7 still to run; tokenDepo is tranquil.
    update = updates.ChangeRuntimeAttributeValue(
        owner=TOKEN_DEPO, attribute="placementCoordinate",
        new_value=_factory_coordinate(x=25.0, y=30.0, degrees=180.0))
    vm.submit(update, ProgramUpdateOption.HOTSWAP)
    # Standing in for the simulation: it sees the update pending, asks
    # whether it may move past frame 1, and waits.
    vm.state.channel.move_request_queue.put(1)

    for _ in range(machines - 3):  # checkpoints before machines 3 to 6: copied while moving
        vm.step()
    assert vm.has_pending_update()

    vm.step()  # checkpoint before machine 7 still sees round 2's copy; machine 7
    assert vm.has_pending_update()  # runs, then round 3 starts: takes question 1, copies while paused

    vm.step()  # checkpoint before round 3's machine 1: tokenDepo is tranquil, so it is applied
    assert not vm.has_pending_update()


# --- AtomicUpdate: a list of updates applied as one (design doc, Topic 9) ---
# Written ahead of the implementation. `updates.AtomicUpdate` is looked up on
# the module inside each test, so that until it exists each test fails on its
# own rather than the whole module failing to collect.

DEPO_BEFORE = {"x": "20.0", "y": "35.0", "degrees": "270.0"}
FEEDER_BEFORE = {"x": "13.0", "y": "20.0", "degrees": "0.0"}


def _move_depo_and_feeder(feeder_attribute: str = "placementCoordinate"):
    """An AtomicUpdate moving tokenDepo and cbFeeder together; a misspelled
    `feeder_attribute` makes its second member fail."""
    return updates.AtomicUpdate([
        updates.ChangeRuntimeAttributeValue(
            owner=TOKEN_DEPO, attribute="placementCoordinate",
            new_value=_factory_coordinate(x=25.0, y=30.0, degrees=180.0)),
        updates.ChangeRuntimeAttributeValue(
            owner=CB_FEEDER, attribute=feeder_attribute,
            new_value=_factory_coordinate(x=15.0, y=22.0, degrees=90.0)),
    ])


def test_atomic_update_waits_until_every_affected_part_is_tranquil():
    # Every member's condition must hold at the same checkpoint: tokenDepo
    # alone being tranquil isn't enough while cbFeeder is moving.
    vm = _build()
    update = _move_depo_and_feeder()
    vm.submit(update, ProgramUpdateOption.HOTSWAP)

    _publish_and_refresh(vm, {
        TOKEN_DEPO: _token_depo_values(receiverSens=False),
        CB_FEEDER: _conveyor_belt_values(currentCommand=ConveyorCommandKind.MOVE_TO_SENSOR),
    })
    vm.step()
    assert vm.has_pending_update()
    assert _placement_coordinate(vm, TOKEN_DEPO) == DEPO_BEFORE
    assert _placement_coordinate(vm, CB_FEEDER) == FEEDER_BEFORE

    _publish_and_refresh(vm, {
        TOKEN_DEPO: _token_depo_values(receiverSens=False),
        CB_FEEDER: _conveyor_belt_values(),
    })
    vm.step()
    assert not vm.has_pending_update()
    assert _placement_coordinate(vm, TOKEN_DEPO) == {"x": "25.0", "y": "30.0", "degrees": "180.0"}
    assert _placement_coordinate(vm, CB_FEEDER) == {"x": "15.0", "y": "22.0", "degrees": "90.0"}


def test_atomic_update_with_a_failing_member_changes_nothing():
    # cbFeeder doesn't redefine `placementCoordinat`: the second member can't
    # be applied, so the first must not be either. Every member is checked
    # before any is applied.
    vm = _build()
    _publish_and_refresh(vm, {
        TOKEN_DEPO: _token_depo_values(receiverSens=False),
        CB_FEEDER: _conveyor_belt_values(),
    })
    vm.submit(_move_depo_and_feeder(feeder_attribute="placementCoordinat"), ProgramUpdateOption.HOTSWAP)

    with pytest.raises(LookupError):
        vm.step()
    assert _placement_coordinate(vm, TOKEN_DEPO) == DEPO_BEFORE
    assert _placement_coordinate(vm, CB_FEEDER) == FEEDER_BEFORE


def test_applied_atomic_update_sends_one_batch_for_every_affected_part():
    # The simulation applies the whole group in the same frame: one batch
    # carrying both parts' new values.
    vm = _build()
    _publish_and_refresh(vm, {
        TOKEN_DEPO: _token_depo_values(receiverSens=False),
        CB_FEEDER: _conveyor_belt_values(),
        VGR: _vgr_values(),
    })
    vm.submit(_move_depo_and_feeder(), ProgramUpdateOption.HOTSWAP)
    _step_round(vm)
    assert not vm.has_pending_update()

    [batch] = _drain(vm.state.channel.model_update_queue)
    assert batch == [
        synchronization.SetAttributeCommand(TOKEN_DEPO, {"placementCoordinate": ("FactoryCoordinate", {"x": 25.0, "y": 30.0, "degrees": 180.0})}),
        synchronization.SetAttributeCommand(CB_FEEDER, {"placementCoordinate": ("FactoryCoordinate", {"x": 15.0, "y": 22.0, "degrees": 90.0})}),
    ]


# --- AddPartInstantiation: a live addition of a part ---
# Written ahead of the implementation. `updates.AddPartInstantiation` is looked
# up on the module inside each test, so that until it exists each test fails on
# its own rather than the whole module failing to collect.

NEW_DEPO = "Main::tokenDepo2"
TOKEN_DEPO_MACHINE = "TokenDepoSystem::TokenDepo::TokenDepoMachine"
NEW_DEPO_AT = {"x": 32.0, "y": 35.0, "degrees": 270.0}


def _add_second_depo():
    """An update adding a second token depot, unbound to any state machine,
    in the empty top-right of the floor."""
    return updates.AddPartInstantiation(
        qualified_name=NEW_DEPO, part_def=TOKEN_DEPO_MACHINE,
        attribute_values={"placementCoordinate": _factory_coordinate(**NEW_DEPO_AT)})


def test_added_part_needs_only_the_language_safe_point():
    # A new part has no running state and nothing bound to it, so adding it is
    # always tranquil: it is applied at the first checkpoint even though no
    # running part is tranquil (tokenDepo holds a token, the others haven't
    # been published).
    vm = _build()
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=True)})
    vm.submit(_add_second_depo(), ProgramUpdateOption.HOTSWAP)
    vm.step()

    assert not vm.has_pending_update()
    part = vm.state.sysml.lookup_table_part_instantiations.get_reference(NEW_DEPO).element_type
    assert part.part_def_origin.qualified_name == TOKEN_DEPO_MACHINE
    assert _placement_coordinate(vm, NEW_DEPO) == {"x": "32.0", "y": "35.0", "degrees": "270.0"}


def test_adding_a_part_under_a_taken_name_leaves_the_running_part_alone():
    # The registry keys parts by qualified name: adding one under a running
    # part's name would silently replace that part. The update is refused
    # instead, and the running tokenDepo stays as it was.
    vm = _build()
    table = vm.state.sysml.lookup_table_part_instantiations
    running = table.get_reference(TOKEN_DEPO).element_type
    vm.submit(updates.AddPartInstantiation(
        qualified_name=TOKEN_DEPO, part_def=TOKEN_DEPO_MACHINE,
        attribute_values={"placementCoordinate": _factory_coordinate(**NEW_DEPO_AT)}), ProgramUpdateOption.HOTSWAP)

    with pytest.raises(ValueError):
        vm.step()
    assert table.get_reference(TOKEN_DEPO).element_type is running
    assert _placement_coordinate(vm, TOKEN_DEPO) == DEPO_BEFORE


def test_atomic_update_adding_a_part_waits_for_the_other_members_parts():
    # Adding a part is always tranquil, but as a member of an AtomicUpdate it
    # isn't applied ahead of the group: nothing changes while tokenDepo, which
    # the other member moves, holds a token; both changes happen together once
    # it is tranquil.
    vm = _build()
    vm.submit(updates.AtomicUpdate([
        _add_second_depo(),
        updates.ChangeRuntimeAttributeValue(
            owner=TOKEN_DEPO, attribute="placementCoordinate",
            new_value=_factory_coordinate(x=25.0, y=30.0, degrees=180.0)),
    ]), ProgramUpdateOption.HOTSWAP)
    table = vm.state.sysml.lookup_table_part_instantiations

    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=True)})
    vm.step()
    assert vm.has_pending_update()
    assert table.get_reference(NEW_DEPO) is None
    assert _placement_coordinate(vm, TOKEN_DEPO) == DEPO_BEFORE

    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=False)})
    vm.step()
    assert not vm.has_pending_update()
    assert table.get_reference(NEW_DEPO) is not None
    assert _placement_coordinate(vm, TOKEN_DEPO) == {"x": "25.0", "y": "30.0", "degrees": "180.0"}


def test_update_to_an_added_part_waits_for_its_tranquility():
    # An added part takes part in tranquility like a startup part, through its
    # part def's #Tranquility constraint (TokenDepoMachine: no token at the
    # receiver). Moving it waits until the simulation has published it, then
    # until its receiver is free.
    vm = _build()
    vm.submit(_add_second_depo(), ProgramUpdateOption.HOTSWAP)
    vm.step()
    assert not vm.has_pending_update()

    vm.submit(updates.ChangeRuntimeAttributeValue(
        owner=NEW_DEPO, attribute="placementCoordinate",
        new_value=_factory_coordinate(x=32.0, y=30.0, degrees=270.0)), ProgramUpdateOption.HOTSWAP)

    # Not published yet: its condition can't be confirmed.
    vm.step()
    assert vm.has_pending_update()

    # A token at its receiver: not tranquil.
    _publish_and_refresh(vm, {NEW_DEPO: _token_depo_values(receiverSens=True)})
    vm.step()
    assert vm.has_pending_update()
    assert _placement_coordinate(vm, NEW_DEPO) == {"x": "32.0", "y": "35.0", "degrees": "270.0"}

    # The receiver is free: applied.
    _publish_and_refresh(vm, {NEW_DEPO: _token_depo_values(receiverSens=False)})
    vm.step()
    assert not vm.has_pending_update()
    assert _placement_coordinate(vm, NEW_DEPO) == {"x": "32.0", "y": "30.0", "degrees": "270.0"}


# --- RemovePartInstantiation: a live removal of a part ---
# Written ahead of the implementation. `updates.RemovePartInstantiation` is
# looked up on the module inside each test, so that until it exists each test
# fails on its own rather than the whole module failing to collect.

def test_removed_part_waits_for_its_tranquility():
    # A removal waits for the removed part's own #Tranquility constraint
    # (TokenDepoMachine: no token at the receiver). The part is the second
    # depot added live, which no state machine binds.
    vm = _build()
    vm.submit(_add_second_depo(), ProgramUpdateOption.HOTSWAP)
    vm.step()
    assert not vm.has_pending_update()
    table = vm.state.sysml.lookup_table_part_instantiations

    vm.submit(updates.RemovePartInstantiation(owner=NEW_DEPO), ProgramUpdateOption.HOTSWAP)

    # Not published yet: its condition can't be confirmed.
    vm.step()
    assert vm.has_pending_update()
    assert table.get_reference(NEW_DEPO) is not None

    # A token at its receiver: not tranquil.
    _publish_and_refresh(vm, {NEW_DEPO: _token_depo_values(receiverSens=True)})
    vm.step()
    assert vm.has_pending_update()
    assert table.get_reference(NEW_DEPO) is not None

    # The receiver is free: removed.
    _publish_and_refresh(vm, {NEW_DEPO: _token_depo_values(receiverSens=False)})
    vm.step()
    assert not vm.has_pending_update()
    assert table.get_reference(NEW_DEPO) is None


def test_removing_a_part_that_isnt_running_is_refused():
    # An update naming a part that isn't running (e.g. a typo in an update
    # file) can't be applied at all; check() refuses it, so the driver rejects
    # the file before submitting it. Unlike a dangling pointer, this is about
    # the update itself, not about the rest of the model.
    vm = _build()
    with pytest.raises(LookupError):
        updates.RemovePartInstantiation(owner="Main::noSuchPart").check(vm.state)

# --- A binding to a missing part ---
# Dangling pointers (e.g. a part removed without re-appointing its state
# machines) are the language user's to avoid: the VM doesn't refuse such a
# removal. The interpreter reports the dangling binding where it is used,
# naming it, instead of resolving it to None.

def test_removal_without_re_appointment_is_reported_where_the_binding_is_used():
    # tokenDepo is removed, but tokenDepoMission still binds it
    # (`in tokenDepoInstance = tokenDepo;`); in Idle it reads
    # `tokenDepoInstance.receiverSens` every step.
    vm = _build()
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=False)})
    vm.submit(updates.RemovePartInstantiation(owner=TOKEN_DEPO), ProgramUpdateOption.HOTSWAP)

    with pytest.raises(LookupError) as error:
        _step_round(vm)

    assert vm.state.sysml.lookup_table_part_instantiations.get_reference(TOKEN_DEPO) is None
    message = str(error.value)
    assert "Main::tokenDepoMission" in message
    assert "tokenDepoInstance" in message
    assert TOKEN_DEPO in message
