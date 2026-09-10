from core.language import Scenario
from core.vm import VirtualMachine

from languages.sysmlv2 import runtime as rt
from languages.sysmlv2.syntax import StateUsage
from languages.sysmlv2.updates import RemessageTransitionEffect, RerouteTransition

from tools.load_xmi_with_syntax import load


PKG = "SimpleSimulationPackage"
STATE_DEF = f"{PKG}::MySimulationDefinition"
IDLE = f"{STATE_DEF}::Idle"
NEXT = f"{STATE_DEF}::Next"


# --- Helpers ---

def _vm_at_idle() -> VirtualMachine:
    """Load the simple model and step it to the point where `main` has run its
    entry action and settled in Idle (quiescent) -- mirrors the stepping in
    tests/test_sysmlv2.py::test_simple_sysmlv2_example_with_behaviour."""
    resource = load("tests/test_sysmlv2-simple.xmi")
    scenario = Scenario(program_definition=resource.contents[0])
    vm = VirtualMachine()
    vm.scenario = scenario
    vm.init()
    vm.step()  # build/registry pass
    vm.step()  # entry -> Idle
    return vm


def _main(vm):
    return vm.state.sysml.lookup_table_executable_state_usages.records[0].element_type


def _idle_trans(vm):
    return vm.state.sysml.lookup_table_item_defs.get_reference(f"{PKG}::IdleTrans").element_type


def _idle_to_next_effect(vm):
    idle = vm.state.sysml.lookup_table_state_defs.get_reference(STATE_DEF).element_type.get_substate(IDLE)
    return idle.contained_transitions[0].effect


# --- Checkpoint marking ---

def test_state_usage_is_a_before_checkpoint():
    node = StateUsage()
    assert node.isUpdatePoint() is True
    assert node.isUpdateBefore() is True
    assert node.isUpdateAfter() is False


# --- Quiescent condition ---

def test_quiescent_condition_true_at_idle():
    vm = _vm_at_idle()
    assert _main(vm).current.qualified_name == IDLE
    assert RemessageTransitionEffect(STATE_DEF, IDLE, "x").condition(vm.state) is True


def test_quiescent_condition_false_with_pending_event():
    vm = _vm_at_idle()
    _main(vm).pending.append(rt.EventOccurrence(event_type=_idle_trans(vm)))
    assert RemessageTransitionEffect(STATE_DEF, IDLE, "x").condition(vm.state) is False


# --- RemessageTransitionEffect: migration changes running behavior ---

def test_remessage_transition_effect_changes_printed_output(capsys):
    vm = _vm_at_idle()
    main = _main(vm)
    assert main.current.qualified_name == IDLE
    capsys.readouterr()  # drop the "Entry" from the entry action

    vm._pending_update = RemessageTransitionEffect(
        state_def=STATE_DEF, source_substate=IDLE, new_message="Bonjour")

    # main is quiescent -> the update is applied at the next before-checkpoint,
    # before the reactive pass; no event pending, so the machine stays at Idle.
    vm.step()
    assert vm._pending_update is None
    assert _idle_to_next_effect(vm).arguments[0].value.el == "Bonjour"

    # Fire Idle -> Next: the migrated message is what gets printed.
    main.pending.append(rt.EventOccurrence(event_type=_idle_trans(vm)))
    vm.step()
    assert main.current.qualified_name == NEXT
    assert capsys.readouterr().out.splitlines() == ["Bonjour"]


def test_update_waits_until_quiescent(capsys):
    vm = _vm_at_idle()
    main = _main(vm)
    capsys.readouterr()

    # Inject the triggering event first, so the machine is NOT quiescent when
    # the checkpoint is reached.
    main.pending.append(rt.EventOccurrence(event_type=_idle_trans(vm)))
    update = RemessageTransitionEffect(
        state_def=STATE_DEF, source_substate=IDLE, new_message="Bonjour")
    vm._pending_update = update

    vm.step()

    # The update was held back (not quiescent), so the transition fired with
    # the original message and the update is still pending.
    assert vm._pending_update is update
    assert main.current.qualified_name == NEXT
    assert capsys.readouterr().out.splitlines() == ["Hello World"]


# --- RerouteTransition: migration changes where the machine goes ---

def test_reroute_transition_redirects_the_machine(capsys):
    vm = _vm_at_idle()
    main = _main(vm)
    capsys.readouterr()

    # Reroute Idle -> Next into a self-loop Idle -> Idle.
    vm._pending_update = RerouteTransition(
        state_def=STATE_DEF, source_substate=IDLE, new_target_substate=IDLE)
    vm.step()
    assert vm._pending_update is None

    idle = vm.state.sysml.lookup_table_state_defs.get_reference(STATE_DEF).element_type.get_substate(IDLE)
    assert idle.contained_transitions[0].target.qualified_name == IDLE

    # Firing IdleTrans now keeps the machine at Idle instead of moving to Next.
    main.pending.append(rt.EventOccurrence(event_type=_idle_trans(vm)))
    vm.step()
    assert main.current.qualified_name == IDLE
