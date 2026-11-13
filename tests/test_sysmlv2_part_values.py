"""Parts A and B of the models@runtime design (Language-Safe-and-Execution-Tranquility-points.md,
Topic 12). Part A: each VM round, the simulation's published values for every
part are copied onto its PartInstantiation, and read through
PartInstantiation.observed_value(name). Part B: `when` conditions read those
values too, instead of the snapshot.

Written ahead of the implementation. `syntax.refresh_part_values` is looked up
on the module inside each test, so that until it exists each test fails on its
own rather than the whole module failing to collect.
"""

import types

import pytest

from core.language import Scenario
from core.vm import VirtualMachine

from languages.sysmlv2 import syntax
from languages.sysmlv2.simulation_models.facade_proxy import PartNotReadyError

from tools.load_xmi_with_syntax import load


XMI = "tests/complete-interesting-simulation.xmi"
TOKEN_DEPO = "Main::tokenDepo"


# --- Helpers ---

def _build() -> VirtualMachine:
    """Load the model and run the build/registry pass."""
    vm = VirtualMachine()
    vm.scenario = Scenario(program_definition=load(XMI).contents[0])
    vm.init()
    vm.step()
    return vm


def _token_depo_values(**overrides) -> types.SimpleNamespace:
    """A simulation-side value object for a TokenDepoMachine, holding exactly
    the attributes the part def declares in SysML."""
    values = dict(tokenCount=0, receiverSens=False, currentCommand=None, placementCoordinate=None)
    values.update(overrides)
    return types.SimpleNamespace(**values)


def _publish_and_refresh(vm: VirtualMachine, snapshot: dict) -> None:
    """Stand in for the simulation publishing `snapshot`, then refresh the
    part instantiations from it."""
    vm.state.channel.latest_snapshot.publish(snapshot)
    syntax.refresh_part_values(
        vm.state.channel,
        vm.state.sysml.lookup_table_part_defs,
        syntax.get_part_instantiations(vm.state.sysml.lookup_table_part_instantiations))


def _part(vm: VirtualMachine, part_usage: str):
    return vm.state.sysml.lookup_table_part_instantiations.get_reference(part_usage).element_type


# --- Tests ---

def test_refresh_copies_the_published_values_onto_the_part():
    vm = _build()
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(tokenCount=7, receiverSens=True)})
    depo = _part(vm, TOKEN_DEPO)
    assert depo.observed_value("tokenCount") == 7
    assert depo.observed_value("receiverSens") is True


def test_refresh_replaces_the_previous_values():
    vm = _build()
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=True)})
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=False)})
    assert _part(vm, TOKEN_DEPO).observed_value("receiverSens") is False


def test_part_missing_from_the_snapshot_is_not_ready():
    # Startup: the simulation hasn't created the part yet.
    vm = _build()
    _publish_and_refresh(vm, {})
    with pytest.raises(PartNotReadyError):
        _part(vm, TOKEN_DEPO).observed_value("receiverSens")


def test_refresh_raises_when_a_declared_attribute_is_missing():
    # The simulation doesn't fulfil the interface the SysML part def declares.
    vm = _build()
    incomplete = types.SimpleNamespace(receiverSens=False)  # tokenCount, ... missing
    with pytest.raises(AttributeError, match="tokenCount"):
        _publish_and_refresh(vm, {TOKEN_DEPO: incomplete})


def test_vm_round_refreshes_the_part_values():
    # Wiring: read_events_and_execute calls the refresh once per round. A VM
    # step stops before each state machine's pass, so stepping through one
    # full round (one step per state machine) reaches the next refresh.
    vm = _build()
    vm.state.channel.latest_snapshot.publish({TOKEN_DEPO: _token_depo_values(receiverSens=True)})
    for _ in vm.state.sysml.lookup_table_executable_state_usages.records:
        vm.step()
    assert _part(vm, TOKEN_DEPO).observed_value("receiverSens") is True


# --- Part B: `when` conditions read the observed values ---

TOKEN_DEPO_MISSION = "Main::tokenDepoMission"


def _substate(vm: VirtualMachine, state_usage, name: str):
    """The substate `name` of `state_usage`'s state def."""
    state_def = vm.state.sysml.lookup_table_state_defs.get_reference(
        state_usage.state_def_origin.qualified_name).element_type
    return next(substate for substate in state_def.substates if substate.name == name)


def test_when_condition_reads_the_observed_values_not_the_snapshot():
    # The simulation publishes again after the round's refresh: a `when`
    # condition still sees the refreshed values, the same ones tranquility
    # reads, not the newer snapshot.
    vm = _build()
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=True)})
    vm.state.channel.latest_snapshot.publish({TOKEN_DEPO: _token_depo_values(receiverSens=False)})

    # The condition only needs the mission's bound arguments (tokenDepoInstance),
    # so set the running state machine directly instead of stepping the VM.
    mission = vm.state.sysml.lookup_table_executable_state_usages.get_reference(TOKEN_DEPO_MISSION).element_type
    vm.state.execution_context.current_state_usage = mission

    # `state Idle; accept when tokenDepoInstance.receiverSens == true ... then CheckCapacity;`
    [idle_to_check_capacity] = _substate(vm, mission, "Idle").contained_transitions
    assert idle_to_check_capacity.trigger.evaluate(vm.state) is True
