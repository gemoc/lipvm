import types

import pytest

from core.vm import *
from core.language import Scenario

from languages.sysmlv2.syntax import *
from languages.sysmlv2 import runtime as rt
from languages.sysmlv2.simulation_models.facade_proxy import SimulationBridge
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.enums import ConveyorCommandKind, DirectionKind

from tools.load_sysml import load

MODEL_PATH = "tools/sysml_test_models/complete-ft-simulation.sysml"


class MockFactory:
    """Dumb recorder standing in for a real Factory at exactly the seam
    on_tick() drives it through (instantiate_machine/execute_action/
    drain_events/build_snapshot) -- for tests that want to check
    interpreter runtime state (vm.state.sysml / rt.*) without also having
    to drive Factory's own physics (real machines, real token movement,
    real encoder pacing) just to produce the simulation-side values that
    state depends on.

    instantiate_machine()/execute_action() do nothing but record the call
    -- no machine registry, no validation that a name was ever
    instantiated, no side effects -- so what the interpreter *decided to
    do* can be asserted on directly (self.instantiate_calls/action_calls).
    drain_events()/build_snapshot() return whatever the test staged via
    self.staged_events/self.staged_snapshot for that tick, standing in for
    what a real Factory.tick() would otherwise have computed physically.

    Deliberately has no tick() -- there's no physics here to advance.
    "Ticking" this mock forward means staging the next
    events/snapshot and letting on_tick()/interpreter_step() drain and
    publish them as usual.

    No model-compliance checking lives here either (e.g. verifying a
    recorded action_name is one the SysML model actually declares for that
    part) -- that's left to whatever assertions a given test writes against
    the recorded calls, case-by-case, not baked into the recorder itself.
    """

    def __init__(self):
        self.instantiate_calls: list[tuple[str, str, dict]] = []
        self.action_calls: list[tuple[str, str, dict]] = []
        self.staged_events: list[tuple[str, str | None]] = []
        self.staged_snapshot: dict = {}

    def instantiate_machine(self, qualified_name: str, part_def_name: str, attrs: dict) -> None:
        self.instantiate_calls.append((qualified_name, part_def_name, attrs))

    def execute_action(self, qualified_name: str, action_name: str, args: dict) -> None:
        self.action_calls.append((qualified_name, action_name, args))

    def drain_events(self) -> list[tuple[str, str | None]]:
        events, self.staged_events = self.staged_events, []
        return events

    def build_snapshot(self) -> dict:
        return self.staged_snapshot


def on_tick(vm: VirtualMachine, factory: MockFactory) -> None:
    """The simulation-thread half of one frame -- verbatim copy of
    on_tick()'s body from main_lipvm_dtsimulation.py's main(). Drains
    whatever the interpreter side queued onto vm.state.channel since the
    last call (instantiate first, so a part created this call already
    exists for the action-drain/snapshot-publish that follow), then
    republishes a fresh snapshot.
    """
    channel = vm.state.channel

    while not channel.instantiate_queue.empty():
        command = channel.instantiate_queue.get_nowait()
        factory.instantiate_machine(command.qualified_name, command.part_def_name, command.attrs)

    while not channel.action_queue.empty():
        command = channel.action_queue.get_nowait()
        factory.execute_action(command.qualified_name, command.action_name, command.args)

    for item_name, source_qualified_name in factory.drain_events():
        SimulationBridge.emit_event(channel, item_name, source_qualified_name)

    channel.latest_snapshot.publish(factory.build_snapshot())


def interpreter_step(vm: VirtualMachine, factory: MockFactory) -> None:
    """One controlled interpreter tick: exactly one vm.step() -- per
    core/vm.py's own step()/is_step docstring, this runs every pending
    operation up to (not including) the next ExecutableStateUsage's own
    evaluate() call, so it advances at most one running mission's reactive
    pass -- then immediately drains whatever that step just queued onto
    Factory (instantiate/action commands), same as on_tick() does after a
    real render frame, so factory/vm.state.sysml never fall out of sync
    between here and your next assertion.
    """
    vm.step()
    on_tick(vm, factory)


@pytest.fixture
def lipvm_based_sysml_interpreter():
    """Builds the VM + Factory pre-condition for a Fischertechnik
    dt-simulation test -- single-threaded, no run_interpreter_loop/pygame
    involved. Loads MODEL_PATH, constructs the Scenario/VirtualMachine
    (vm.init()'d but not yet stepped) and a fresh Factory (nothing
    instantiated yet -- that only happens once interpreter_step() drains
    the first InstantiateCommand).

    Yields (vm, factory). Drive the simulation yourself from the test body
    with interpreter_step(vm, factory) / simulation_tick(vm, factory),
    interleaved however your scenario needs, with plain assertions on
    vm.state.sysml / factory in between each call.
    """
    resource = load(MODEL_PATH, keep_xmi=False)
    root = resource.contents[0]
    scenario = Scenario(program_definition=root)

    vm = VirtualMachine()
    vm.scenario = scenario
    vm.init()

    yield vm


def test_token_producer_platform_sensor_edge(lipvm_based_sysml_interpreter):
    """
    A unit test to check if the interpreter send an action to produce a token to a Token Producer machine
    """

    factory = MockFactory()

    # Given part
    # It is expected that there is a token produce machine named tokenProd with its state machine called
    # tokenProducerMission in the input SysML model. Such a condition exists knowing that there
    # are multiple state machines (Missions) to be executed by the interpreter
    tp_qualified_name = "Main::tokenProd"
    mission_qualified_name = "Main::tokenProducerMission"
    mission_stats = {
        record.qualified_name: record.element_type
        for record in lipvm_based_sysml_interpreter.state.sysml.lookup_table_executable_state_usages.records
    }

    # When: calling a step to the interpreter, at some point, there is an action called by a state machine
    # controlling the token producer to emit a token with a random color. Since we are unsure when this action
    # is called, we specify a step budget (a number of steps called to the interpreter) that we know, at some point
    # the emit token action will be called.
    STEP_BUDGET = 20
    for _ in range(STEP_BUDGET):
        if factory.action_calls:
            break
        interpreter_step(lipvm_based_sysml_interpreter, factory)
    else:
        pytest.fail(f"tokenProd never received an action within {STEP_BUDGET} interpreter steps")

    # Then: the interpreter issued exactly randomEmitToken -- purely what
    # it decided to do (recorded by the mock), not anything a real Factory
    # computed -- and tokenProducerMission's own state confirms it's the
    # entry chain that issued it.
    assert factory.action_calls == [(tp_qualified_name, "randomEmitToken", {})]
    assert (mission_stats[mission_qualified_name].current.qualified_name ==
            "TokenProducerSystem::TokenProducerStates::TokenProducerSimpleMission::ProducingTokenRandomly")

    # When: At the moment when a token is emitted, two event messages must be sent
    # Success message (token is emitted) and the token exist in the platform, thereby the
    # platform is busy.
    factory.staged_events = [
        ("TokenProducerSuccessEventMessage", tp_qualified_name),
        ("TokenPlatformBusyEventMessage", tp_qualified_name),
    ]
    factory.staged_snapshot = {tp_qualified_name: types.SimpleNamespace(platformSens=True)}
    wait_platform_free_state = (
        "TokenProducerSystem::TokenProducerStates::TokenProducerSimpleMission::WaitPlatformFree"
    )

    # Then: tokenProducerMission moves on to WaitPlatformFree -- and, since
    # the staged snapshot still reads platformSens == True, it stays there
    # rather than bouncing straight back to ProducingTokenRandomly via its
    # own `accept when tokenProducerMachine.platformSens == false` (the
    # loop below fails the test outright if that isn't what happens).
    for _ in range(STEP_BUDGET):
        if mission_stats[mission_qualified_name].current.qualified_name == wait_platform_free_state:
            break
        interpreter_step(lipvm_based_sysml_interpreter, factory)
    else:
        pytest.fail("tokenProducerMission never reacted to TokenProducerSuccessEventMessage")


def test_token_producer_to_feeder_conveyor_transport(lipvm_based_sysml_interpreter):
    """
    A unit test ensuring a VGR machine will pick a token once it is available
    in the token producer's platform
    """
    vm = lipvm_based_sysml_interpreter
    factory = MockFactory()

    vgr_qualified_name = "Main::vgrPickProducer"
    tp_qualified_name = "Main::tokenProd"
    mission_qualified_name = "Main::vgrProdToFeed"
    idle_state = "VacuumGripperSystem::VGRStates::VGRPickTokenFromProducerAndPlace::Idle"
    wait_for_pickup_state = "VacuumGripperSystem::VGRStates::VGRPickTokenFromProducerAndPlace::WaitForPickup"

    mission_stats = {
        record.qualified_name: record.element_type
        for record in vm.state.sysml.lookup_table_executable_state_usages.records
    }

    def action_names(qualified_name):
        return [call[1] for call in factory.action_calls if call[0] == qualified_name]

    # When: stepped forward -- polled rather than counted, same reasoning
    # as the round-robin ordering elsewhere in this file -- until
    # vgrProdToFeed's own entry chain (entry vgr.setup; then Idle;) has
    # run: an unconditional transition, not gated on any event, so it
    # lands on Idle the very turn vgr.setup is issued.
    STEP_BUDGET = 20
    for _ in range(STEP_BUDGET):
        current = mission_stats[mission_qualified_name].current
        if current is not None and current.qualified_name == idle_state:
            break
        interpreter_step(vm, factory)
    else:
        pytest.fail(f"vgrProdToFeed never reached Idle within {STEP_BUDGET} interpreter steps")

    # Then: vgr.setup was issued to get there, and Idle's own `accept when
    # tokenProducer.platformSens == true` guard hasn't had a true reading
    # to react to yet -- no pick issued.
    assert "setup" in action_names(vgr_qualified_name)
    assert "pick" not in action_names(vgr_qualified_name)

    # When: the simulation reports the token producer's platform sensor as
    # busy -- a token is now available on tokenProd's platform.
    factory.staged_snapshot = {tp_qualified_name: types.SimpleNamespace(platformSens=True)}

    # Then: vgrProdToFeed's Idle guard fires -- it picks up from
    # pickFromProducerPosition (`do vgr.pick { in targetPosition =
    # pickFromProducerPosition; }`) and moves on to WaitForPickup.
    for _ in range(STEP_BUDGET):
        current = mission_stats[mission_qualified_name].current
        if current is not None and current.qualified_name == wait_for_pickup_state:
            break
        interpreter_step(vm, factory)
    else:
        pytest.fail("vgrProdToFeed never reacted to tokenProducer.platformSens becoming true")

    assert "pick" in action_names(vgr_qualified_name)
