import pytest

from core.vm import *
from core.language import Scenario

from languages.sysmlv2.syntax import *
from languages.sysmlv2 import runtime as rt
from languages.sysmlv2.simulation_models.facade_proxy import SimulationBridge
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.enums import ConveyorCommandKind, DirectionKind, \
    TokenProducerCommandKind

from tools.load_sysml import load

MODEL_PATH = "tools/sysml_test_models/complete-ft-simulation.sysml"


def on_tick(vm: VirtualMachine, factory: Factory) -> None:
    """The simulation-thread half of one frame -- verbatim copy of
    on_tick()'s body from main_lipvm_dtsimulation.py's main(). Drains
    whatever the interpreter side queued onto vm.state.channel since the
    last call (instantiate first, so a part created this call already
    exists for the action-drain/snapshot-publish that follow), then
    republishes a fresh snapshot.

    Production calls this from the pygame thread, once per rendered frame,
    with the interpreter's own vm.step() calls running concurrently on a
    background thread -- deliberately not reproduced here. A free-running
    background thread can't be paused between one vm.step() and the next,
    which is exactly the control a test needs to inspect state after every
    individual tick. So this module runs everything on the single test
    thread instead: interpreter_step()/simulation_tick() below call
    vm.step()/factory.tick() directly, one at a time, only when the test
    asks for one -- same bodies as production, just driven synchronously.
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


def interpreter_step(vm: VirtualMachine, factory: Factory) -> None:
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


def simulation_tick(vm: VirtualMachine, factory: Factory) -> None:
    """One controlled simulation tick: exactly one Factory.tick() --
    physically advances every currently non-idle machine by one step --
    then republishes a fresh snapshot, so the next interpreter_step() (e.g.
    an `accept when` guard) sees up-to-date attribute values rather than
    whatever was live before this tick.
    """
    factory.tick()
    on_tick(vm, factory)


def interpreter_round(vm: VirtualMachine, factory: Factory) -> None:
    """Advances the interpreter through exactly one full round-robin pass:
    every currently-registered ExecutableStateUsage gets exactly one
    reactive turn (interpreter_step() N times, N = the number of
    executable state usages, read off vm.state.sysml -- available right
    after vm.init(), no step needed first).

    One nuance, confirmed empirically against complete-ft-simulation.xmi's
    10 missions by logging vm.state.execution_context.current_state_usage
    after every vm.step(): the model's very first reactive pass is preceded
    by one extra interpreter_step() that only does the one-time setup
    (part-instantiation + event-queue drain) and runs no mission at all --
    so round 1 costs N+1 steps, not N. Every round after that costs exactly
    N, with no drift: the next round's own setup silently piggybacks on the
    previous round's final stat-step (core/operation.py's lazy_loop's
    Operation chain splicing does this, not anything the interpreter does
    explicitly). vm.state.execution_context.current_state_usage is None
    only during that one leading setup-only step, before any mission's
    evaluate() has ever run -- exactly the condition that needs the one-off
    extra step, so it's what this checks rather than counting calls.
    """
    if vm.state.execution_context.current_state_usage is None:
        interpreter_step(vm, factory)

    n = len(vm.state.sysml.lookup_table_executable_state_usages.records)
    for _ in range(n):
        interpreter_step(vm, factory)


def pump(vm: VirtualMachine, factory: Factory) -> None:
    """Advances the whole simulated world by one 'frame': every mission
    gets its one round-robin turn (interpreter_round()), then the physical
    world advances by one Factory.tick() (simulation_tick()) -- so every
    mission reacts to one consistent snapshot before it changes again.

    Convenience for a test that wants "run everything forward by one unit"
    without caring about round-robin mechanics. Reach for
    interpreter_step()/simulation_tick() directly instead when you need
    finer control -- e.g. ticking Factory many times while waiting for a
    token to physically travel from one sensor to another, without also
    forcing all 9 *other* missions to re-evaluate that many times (most
    visibly: tokenProducerMission's randomEmitToken firing on every one of
    those ticks, spawning tokens you never asked for).
    """
    interpreter_round(vm, factory)
    simulation_tick(vm, factory)


@pytest.fixture
def dt_simulation():
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
    resource = load(MODEL_PATH)
    root = resource.contents[0]
    scenario = Scenario(program_definition=root)

    vm = VirtualMachine()
    vm.scenario = scenario
    vm.init()

    factory = Factory()

    yield vm, factory


def test_complete_ft_simulation(dt_simulation):
    """One pump() -- one full interpreter round (every mission's first
    turn) plus one physical Factory tick -- should already be enough for
    every mission's own unconditional `entry; then <FirstSubstate>;`
    default transition to fire (see ExecutableStateUsage.evaluate()'s `if
    self.current is None: self._run_entry_behaviour(...)`,
    languages/sysmlv2/runtime.py): nothing here depends on an external
    event or a when-guard, so there's no reason any of the 10 missions
    would still be sitting at current=None afterward.
    """
    vm, factory = dt_simulation

    stats = {
        record.qualified_name: record.element_type
        for record in vm.state.sysml.lookup_table_executable_state_usages.records
    }

    # Given: nothing has run yet -- fresh off vm.init(), before any pump().
    assert all(usage.current is None for usage in stats.values())

    # When: exactly one pump().
    pump(vm, factory)

    # Then: every mission already left current=None -- landed on the first
    # substate named by its own StateDef's default transition.
    expected_first_state = {
        "Main::tokenProducerMission":
            "TokenProducerSystem::TokenProducerStates::TokenProducerSimpleMission::ProducingTokenRandomly",
        "Main::cbFeederMission": "ConveyorBeltSystem::ConveyorBeltStates::ConveyorBeltSimpleMission::Start",
        "Main::cbTransportMission": "ConveyorBeltSystem::ConveyorBeltStates::ConveyorBeltSimpleMission::Start",
        "Main::tokenRedDepoMission": "TokenDepoSystem::TokenDepoStates::TokenDepoSimpleMission::Idle",
        "Main::tokenWhiteDepoMission": "TokenDepoSystem::TokenDepoStates::TokenDepoSimpleMission::Idle",
        "Main::tokenBlueDepoMission": "TokenDepoSystem::TokenDepoStates::TokenDepoSimpleMission::Idle",
        "Main::vgrProdToFeed": "VacuumGripperSystem::VGRStates::VGRPickTokenFromProducerAndPlace::Idle",
        "Main::vgrPickToSort": "VacuumGripperSystem::VGRStates::VGRPickTokenFromCBAndPlace::Idle",
        "Main::vgrMissionFeedTrans": "VacuumGripperSystem::VGRStates::VGRMissionWith2CB::SafePosition",
        "Main::slMission": "SortingLineSystem::SortingLineMissions::SortingLineSimpleMission::Idle",
    }
    assert set(stats) == set(expected_first_state)
    for qualified_name, expected_substate in expected_first_state.items():
        current = stats[qualified_name].current
        assert current is not None, f"{qualified_name} never fired its default transition"
        assert current.qualified_name == expected_substate

    # And: Start's own entry action (`conveyorBelt.moveToSensor { direction
    # = FORWARD }`) already reached the real Factory, not just the
    # interpreter's own bookkeeping -- cbFeeder is a live ConveyorBeltMachine
    # actually mid-command.
    cb_feeder = factory.get_machine("Main::cbFeeder")
    assert cb_feeder is not None
    assert cb_feeder.currentCommand == ConveyorCommandKind.MOVE_TO_SENSOR
    assert cb_feeder.direction == DirectionKind.FORWARD


def test_token_producer_platform_sensor_edge(dt_simulation):
    """tokenProd.platformSens is a live read (whether a Token currently
    sits on platform_position(), via Factory.tokens_on() --
    fischertechnik_parts/token_producer.py) rather than simulation
    bookkeeping, so it can only flip once randomEmitToken's queued command
    has actually been *ticked* on the real Factory -- one tick after the
    interpreter issues it, not at the moment it's issued. Checks that edge
    directly (False before the tick that runs the command, True after),
    then checks the two events TokenProducerMachine raises as a direct
    result: TokenProducerSuccessEventMessage (stop(), the command
    finishing) and TokenPlatformBusyEventMessage (the platformSens rising
    edge itself, detected via FischertechnikMachine._sensor_edge() right
    after that dispatch).
    """
    vm, factory = dt_simulation

    # When: every mission gets its first turn -- tokenProducerMission's own
    # entry chain (entry; then ProducingTokenRandomly; entry
    # tokenProducerMachine.randomEmitToken) queues the ActionCommand, but
    # nothing has been ticked yet.
    interpreter_round(vm, factory)

    tp = factory.get_machine("Main::tokenProd")
    assert tp is not None
    assert tp.currentCommand == TokenProducerCommandKind.RANDOM_EMIT_TOKEN

    # Then: the command is issued but not yet physically run -- no token on
    # the platform, so platformSens still reads False.
    assert tp.platformSens is False
    assert factory.tokens == []

    # When: exactly one physical tick actually executes the queued command.
    # Using factory.tick() directly here (rather than simulation_tick())
    # deliberately skips the drain-into-channel/republish-snapshot step, so
    # the events below can be inspected via drain_events() before anything
    # else consumes them.
    factory.tick()

    # Then: a token now sits on the platform -- platformSens's rising edge.
    assert tp.platformSens is True
    assert len(factory.tokens) == 1
    assert tp.currentCommand == TokenProducerCommandKind.STOP

    # And: Factory recorded exactly those two events for tokenProd, in
    # order -- filtered by source, since this same tick also completes
    # setup() on every VacuumGripperMachine mid-entry (vgr.setup, three of
    # the ten missions), each raising its own unrelated
    # VGRCommandSuccessEventMessage in the same drain.
    events = factory.drain_events()
    token_producer_events = [event for event in events if event[1] == "Main::tokenProd"]
    assert token_producer_events == [
        ("TokenProducerSuccessEventMessage", "Main::tokenProd"),
        ("TokenPlatformBusyEventMessage", "Main::tokenProd"),
    ]

    # A second drain proves drain_events() actually cleared the list,
    # rather than just handing back a live view of it.
    assert factory.drain_events() == []
