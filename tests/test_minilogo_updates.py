from core.language import Scenario, RuntimeState
from core.operation import Operation
from core.vm import VirtualMachine

from languages.minilogo.runtime import (
    PenStatus,
    ColorCode,
    Coordinates,
    Drawing,
    PenState,
    Scope,
)
from languages.minilogo.syntax import Program, Move, Pen, Color, Literal
from languages.minilogo.updates import InsertMove, RemoveCommand, RecolorFromNow


# --- Helpers ---

def _runtime(pen_status=PenStatus.up, color=None) -> RuntimeState:
    return RuntimeState(elements=[
        Drawing(name="drawing"),
        PenState(
            name="penstate",
            color=color if color is not None else ColorCode(r=0, g=0, b=0),
            position=Coordinates(x=0, y=0),
            status=pen_status,
        ),
        Scope(name="scope"),
    ])


def _pending_vm(update, program, current_command, runtime) -> VirtualMachine:
    update.edit_script.attach_to(program)
    vm = VirtualMachine()
    vm._pending_update = update
    vm._runtime = runtime
    vm._operation = Operation(lambda: None, args=(current_command, runtime))
    return vm


# --- InsertMove: structural, gated on pen up ---

def test_insert_move_applies_when_pen_up():
    program = Program(identifier=100, commands=[
        Pen(identifier=1, status=PenStatus.up),
        Pen(identifier=2, status=PenStatus.down),
    ])
    update = InsertMove(program_identifier=100, index=1, x=3, y=4, move_identifier=9)
    vm = _pending_vm(update, program, program.commands[0], _runtime(PenStatus.up))

    vm._apply_pending_update(before=True)

    assert vm._pending_update is None
    assert [c.identifier for c in program.commands] == [1, 9, 2]


def test_insert_move_waits_when_pen_down():
    program = Program(identifier=100, commands=[
        Pen(identifier=1, status=PenStatus.down),
        Pen(identifier=2, status=PenStatus.up),
    ])
    update = InsertMove(program_identifier=100, index=1, x=3, y=4, move_identifier=9)
    vm = _pending_vm(update, program, program.commands[0], _runtime(PenStatus.down))

    vm._apply_pending_update(before=True)

    assert vm._pending_update is update
    assert [c.identifier for c in program.commands] == [1, 2]


# --- RemoveCommand: structural, gated on pen up ---

def test_remove_command_applies_when_pen_up():
    program = Program(identifier=100, commands=[
        Pen(identifier=1, status=PenStatus.up),
        Move(identifier=2, x=Literal(value=1), y=Literal(value=1)),
        Pen(identifier=3, status=PenStatus.down),
    ])
    update = RemoveCommand(program_identifier=100, index=1)
    vm = _pending_vm(update, program, program.commands[0], _runtime(PenStatus.up))

    vm._apply_pending_update(before=True)

    assert vm._pending_update is None
    assert [c.identifier for c in program.commands] == [1, 3]


def test_remove_command_waits_when_pen_down():
    program = Program(identifier=100, commands=[
        Pen(identifier=1, status=PenStatus.down),
        Move(identifier=2, x=Literal(value=1), y=Literal(value=1)),
    ])
    update = RemoveCommand(program_identifier=100, index=1)
    vm = _pending_vm(update, program, program.commands[0], _runtime(PenStatus.down))

    vm._apply_pending_update(before=True)

    assert vm._pending_update is update
    assert [c.identifier for c in program.commands] == [1, 2]


# --- RecolorFromNow: attribute edit + migration of the live pen ---

def test_recolor_edits_command_and_migrates_live_pen():
    color_cmd = Color(identifier=5, colorCode=ColorCode(r=0, g=0, b=0))
    program = Program(identifier=100, commands=[color_cmd])
    runtime = _runtime(PenStatus.up)

    update = RecolorFromNow(color_identifier=5, r=10, g=20, b=30)
    vm = _pending_vm(update, program, color_cmd, runtime)

    vm._apply_pending_update(before=True)

    assert vm._pending_update is None
    # The syntax was edited...
    assert (color_cmd.colorCode.r, color_cmd.colorCode.g, color_cmd.colorCode.b) == (10, 20, 30)
    # ...and the live pen was migrated so the new color is already in effect.
    assert (runtime.penstate.color.r, runtime.penstate.color.g, runtime.penstate.color.b) == (10, 20, 30)


# --- End to end: an inserted move is hot-swapped in and actually runs ---

def test_insert_move_is_picked_up_by_the_running_program():
    program = Program(identifier=100, commands=[
        Pen(identifier=1, status=PenStatus.up),
        Move(identifier=2, x=Literal(value=5), y=Literal(value=5)),
    ])
    scenario = Scenario(program_definition=program)

    vm = VirtualMachine()
    vm.scenario = scenario
    vm.init()

    # Queue an update that appends a Move to (7, 8) after the existing one.
    update = InsertMove(program_identifier=100, index=2, x=7, y=8, move_identifier=9)
    update.edit_script.attach_to(scenario)
    vm._pending_update = update

    vm.run()

    # The move was inserted into the syntax and lazy_loop reached it, so the
    # pen ends at the inserted move's coordinates.
    assert [c.identifier for c in program.commands] == [1, 2, 9]
    assert (vm.state.penstate.position.x, vm.state.penstate.position.y) == (7, 8)
