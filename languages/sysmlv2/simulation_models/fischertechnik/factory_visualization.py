"""Pygame rendering for a Factory: the viewport (grid, floor boundary,
tokens), the side panel, and the run loop. Per-machine-kind drawing lives
in fischertechnik_parts_visualization/ instead (one MachineVisualization
subclass per machine kind, e.g. ConveyorBeltVisualization) -- this file's
own viewport constants/helpers (SCALE/_to_screen/BELT_WIDTH/etc.) are
imported from here into those. Machine classes themselves
(Factory/ConveyorBeltMachine/VacuumGripperMachine/Token) stay free of any
rendering-library object, so they remain usable (and testable)
independent of whether a display is even available.
"""

import itertools
import math
import os
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")  # this file can get imported just for class discovery (see registry.py), not necessarily to actually render -- suppress pygame's own import-time banner so it doesn't pollute stdout for callers who never asked for it
import pygame

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import TokenColorKind
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts.conveyor_belt import FULL_LENGTH
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts_visualization.generic import MachineVisualization
from languages.sysmlv2.simulation_models.fischertechnik.token import Token
from languages.sysmlv2.simulation_models.generic import SimulationVisualization
from languages.sysmlv2.simulation_models.registry import scan_for_subclasses

SCALE = 20                       # pixels per model unit
MODEL_RANGE = 40                 # factory floor spans model coordinates 0..MODEL_RANGE on both x and y

# Wide enough that a token at the FULL_LENGTH boundary -- FULL_LENGTH / 2
# model units from center, the furthest a token can travel while still
# owned (see ConveyorBeltMachine.advance()) -- still visually sits on the
# drawn belt, keeping the same 10px-per-side margin the original design
# had just beyond FEED_TO_SWAP_LENGTH / 2 alone.
BELT_WIDTH = FULL_LENGTH * SCALE + 20

# Model-unit, cross-belt (perpendicular-to-travel) dimension -- purely a
# rendering size, unlike FEED_TO_SWAP_LENGTH/FULL_LENGTH (conveyor_belt.py), which
# also drive movement math. No simulation behavior depends on this value,
# so it lives here rather than in conveyor_belt.py.
BELT_CROSS_WIDTH = 2
BELT_HEIGHT = BELT_CROSS_WIDTH * SCALE


def _floor_layout(model_range: float, scale: int, belt_width: int, belt_height: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """Computes (VIEWPORT_SIZE, ORIGIN) for a `model_range` x `model_range`
    factory floor at the given `scale`. Reserves a uniform pixel margin on
    every edge, sized to half the belt's larger dimension -- enough that a
    belt centered on any boundary coordinate (x or y = 0 or `model_range`),
    in any of its 0/90/180/270 degree placements, still fits on the canvas
    instead of clipping. Model (0, 0) lands exactly on the floor's own
    bottom-left corner (see `_draw_floor_boundary`); the margin is blank
    canvas *outside* that corner, reserved purely for overhang -- a modeler
    writing `placementCoordinate` values never needs to account for it.
    """
    margin = max(belt_width, belt_height) // 2
    size = int(model_range * scale) + 2 * margin
    return (size, size), (margin, size - margin)


VIEWPORT_SIZE, ORIGIN = _floor_layout(MODEL_RANGE, SCALE, BELT_WIDTH, BELT_HEIGHT)  # factory floor drawing area, excludes the attribute panel

PANEL_WIDTH = 500  # wide enough for the longest panel_lines() row seen so far
                    # -- "currentCommand: VacuumGripperCommandKind.MOVE_TO_SAFE_POSITION"
                    # renders at ~461px (default SysFont, size 18); 300 clipped
                    # even ConveyorBeltVisualization's shorter "currentCommand:
                    # ConveyorCommandKind.MOVE_TO_SENSOR" (~376px)
WINDOW_SIZE = (VIEWPORT_SIZE[0] + PANEL_WIDTH, VIEWPORT_SIZE[1])
BACKGROUND_COLOR = (255, 255, 255)

PANEL_X = VIEWPORT_SIZE[0]
PANEL_BACKGROUND_COLOR = (245, 245, 245)
PANEL_DIVIDER_COLOR = (60, 60, 60)
PANEL_TEXT_COLOR = (20, 20, 20)
PANEL_LEFT_PADDING = 16
PANEL_TOP_PADDING = 16
PANEL_LINE_HEIGHT = 20
PANEL_MACHINE_GAP = 14           # extra vertical gap after each machine's block
PANEL_SUMMARY_GAP = 14           # extra vertical gap after the factory-wide summary line

PANEL_BUTTON_TEXT_COLOR = (20, 20, 20)

PANEL_BUTTON_WIDTH = 60          # one of the 4 token-placement buttons per belt
PANEL_BUTTON_HEIGHT = 22
PANEL_BUTTON_GAP = 6             # horizontal gap between buttons in the same row
PANEL_BUTTON_COLOR = (210, 210, 210)
PANEL_BUTTON_HOVER_COLOR = (185, 200, 225)

START_BUTTON_WIDTH = 100
START_BUTTON_HEIGHT = 32
START_BUTTON_COLOR = (150, 200, 150)
START_BUTTON_HOVER_COLOR = (120, 180, 120)

PALETTE_SWATCH_SIZE = 22
PALETTE_SWATCH_GAP = 8
PALETTE_SELECTED_BORDER_COLOR = (20, 20, 20)
PALETTE_UNSELECTED_BORDER_COLOR = (150, 150, 150)

BELT_FRAME_COLOR = (60, 60, 60)      # guide rails, visible along the belt's long edges from above
BELT_SURFACE_COLOR = (35, 35, 35)    # the belt's top surface, inset from the rails
BELT_TREAD_COLOR = (70, 70, 70)      # tread ridges, running across the belt's direction of travel
FEED_COLOR = (40, 160, 90)           # left end, in the belt's own unrotated frame: where parts enter
SWAP_COLOR = (210, 150, 30)          # right end, in the belt's own unrotated frame: where parts exit/swap
TREAD_SPACING = 10
ROLLER_BAND_WIDTH = 6

TOKEN_RADIUS = 8
TOKEN_OUTLINE_COLOR = (60, 60, 60)   # ring around every token; keeps a WHITE token visible against BACKGROUND_COLOR
TOKEN_COLORS = {
    TokenColorKind.BLUE: (30, 90, 200),
    TokenColorKind.WHITE: (255, 255, 255),
    TokenColorKind.RED: (200, 40, 40),
}

GRID_STEP = 5                          # model units between grid lines
GRID_LINE_COLOR = (225, 225, 225)
GRID_AXIS_COLOR = (170, 170, 170)      # the x=0 / y=0 lines, drawn heavier so the origin stands out
GRID_LABEL_COLOR = (140, 140, 140)
FLOOR_BOUNDARY_COLOR = (120, 120, 120) # outlines the (0,0)-(MODEL_RANGE,MODEL_RANGE) floor edge, distinct from the grid lines inside it


def _to_screen(coord: FactoryCoordinate) -> tuple[int, int]:
    """Model coordinate -> screen pixel, via SCALE/ORIGIN. Module-level
    (not a FischertechnikVisualization method) since it carries no
    instance state, and both FischertechnikVisualization itself and every
    per-machine-kind MachineVisualization drawer (e.g.
    ConveyorBeltVisualization) need it.
    """
    px = ORIGIN[0] + coord.x * SCALE
    py = ORIGIN[1] - coord.y * SCALE  # flip y: pygame's screen y grows downward
    return int(px), int(py)

class FischertechnikVisualization(SimulationVisualization):
    """Fischertechnik's SimulationVisualization (generic.py). `run()` is
    the only method ever called from outside this class -- every other
    method below is a private drawing helper, previously a module-level
    function, moved here so the whole rendering surface lives on one
    class instead of being split between free functions and a thin
    wrapper around them.

    `run()`'s own local state (`started`/`selected_color`/`next_token_id`)
    and its nested closures (`handle_start`/`handle_select_color`/
    `handle_place_token`) deliberately stay as plain locals/closures, not
    instance attributes -- they're fresh every call today (each `run()`
    call starts a brand new pygame session), and promoting them to `self.`
    state would change that semantics (state persisting across more than
    one `run()` call on the same instance) as a side effect of a pure
    move, not something asked for.
    """

    def __init__(self):
        """Builds `self._drawers`, a `PartSimulationModel` subclass ->
        `MachineVisualization` instance map, discovered via
        `scan_for_subclasses()` (`registry.py`) rather than hardcoded --
        so `_draw_viewport()` can dispatch on `type(machine)` without
        knowing about any specific machine kind, and a future
        `MachineVisualization` subclass (e.g. for `VacuumGripperMachine`)
        needs no change here to be picked up.
        """
        self._drawers = {klass.machine_type: klass() for klass in scan_for_subclasses(MachineVisualization).values()}

    def _visible_model_range(self, axis_min_px: int, axis_max_px: int, origin_px: float, flip: bool, step: int) -> range:
        """Model-unit values (multiples of `step`) whose grid line falls inside
        `[axis_min_px, axis_max_px]` on screen, for one axis at a time. `flip`
        accounts for the y-axis running opposite to pygame's screen-space
        (see `_to_screen`), so both axes can share this one helper.
        """
        if flip:
            lo_unit = (origin_px - axis_max_px) / SCALE
            hi_unit = (origin_px - axis_min_px) / SCALE
        else:
            lo_unit = (axis_min_px - origin_px) / SCALE
            hi_unit = (axis_max_px - origin_px) / SCALE
        return range(math.ceil(lo_unit / step) * step, math.floor(hi_unit / step) * step + 1, step)

    def _draw_grid(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """Draws a light reference grid, one line every `GRID_STEP` model units,
        labeled with the model coordinate each line represents -- so a
        developer placing a new `part`'s `placementCoordinate` can look at this
        grid and see directly where in the viewport that (x, y) will land,
        instead of having to compute it from `SCALE`/`ORIGIN` by hand. Confined
        to the viewport (excludes the side panel), drawn first so belts/tokens
        render on top of it.
        """
        for gx in self._visible_model_range(0, VIEWPORT_SIZE[0], ORIGIN[0], flip=False, step=GRID_STEP):
            px, _ = _to_screen(FactoryCoordinate(gx, 0, 0))
            color = GRID_AXIS_COLOR if gx == 0 else GRID_LINE_COLOR
            pygame.draw.line(screen, color, (px, 0), (px, VIEWPORT_SIZE[1]), 2 if gx == 0 else 1)
            label = font.render(str(gx), True, GRID_LABEL_COLOR)
            screen.blit(label, (px + 2, 2))

        for gy in self._visible_model_range(0, VIEWPORT_SIZE[1], ORIGIN[1], flip=True, step=GRID_STEP):
            _, py = _to_screen(FactoryCoordinate(0, gy, 0))
            color = GRID_AXIS_COLOR if gy == 0 else GRID_LINE_COLOR
            pygame.draw.line(screen, color, (0, py), (VIEWPORT_SIZE[0], py), 2 if gy == 0 else 1)
            label = font.render(str(gy), True, GRID_LABEL_COLOR)
            screen.blit(label, (2, py + 2))

    def _draw_floor_boundary(self, screen: pygame.Surface) -> None:
        """Outlines the (0, 0)-(MODEL_RANGE, MODEL_RANGE) floor rect, so the
        origin corner `_floor_layout` promises is actually visible on screen
        rather than just implied by where the grid's axis lines cross. The
        margin `_floor_layout` reserves around this rect is deliberately
        blank outside it -- overhang room for a belt centered on a boundary
        coordinate, not part of the floor itself.
        """
        top_left = _to_screen(FactoryCoordinate(0, MODEL_RANGE, 0))
        bottom_right = _to_screen(FactoryCoordinate(MODEL_RANGE, 0, 0))
        rect = pygame.Rect(top_left[0], top_left[1], bottom_right[0] - top_left[0], bottom_right[1] - top_left[1])
        pygame.draw.rect(screen, FLOOR_BOUNDARY_COLOR, rect, width=2)

    def _draw_token(self, screen: pygame.Surface, token: Token) -> None:
        """Draws a Token as a small filled circle at its current position, on
        top of whatever machine it's sitting on, colored by its TokenColorKind.
        """
        px, py = _to_screen(token.position)
        pygame.draw.circle(screen, TOKEN_COLORS[token.color], (px, py), TOKEN_RADIUS)
        pygame.draw.circle(screen, TOKEN_OUTLINE_COLOR, (px, py), TOKEN_RADIUS, 1)

    def _draw_start_panel(self, screen: pygame.Surface, font: pygame.font.Font, label_font: pygame.font.Font,
                           on_start_click) -> list[tuple[pygame.Rect, object]]:
        """Draws the side panel before the simulation has started: just a
        "Start" button and a short instruction -- no per-machine blocks, since
        no part has been instantiated yet (see main_lipvm_dtsimulation.py's
        `on_start`, which only runs -- and only then populates `factory.machines`
        -- once this button is actually clicked).

        Same (rect, callback) return shape as `_draw_machine_panel()`, so
        `run()`'s event loop hit-tests both the same way regardless of
        which panel is currently showing.
        """
        panel_rect = pygame.Rect(PANEL_X, 0, PANEL_WIDTH, VIEWPORT_SIZE[1])
        pygame.draw.rect(screen, PANEL_BACKGROUND_COLOR, panel_rect)
        pygame.draw.line(screen, PANEL_DIVIDER_COLOR, (PANEL_X, 0), (PANEL_X, VIEWPORT_SIZE[1]), 2)

        x = PANEL_X + PANEL_LEFT_PADDING
        y = PANEL_TOP_PADDING

        screen.blit(label_font.render("Simulation not started", True, PANEL_TEXT_COLOR), (x, y))
        y += PANEL_LINE_HEIGHT
        screen.blit(font.render("Click Start to instantiate the", True, PANEL_TEXT_COLOR), (x, y))
        y += PANEL_LINE_HEIGHT
        screen.blit(font.render("model's parts and begin.", True, PANEL_TEXT_COLOR), (x, y))
        y += PANEL_LINE_HEIGHT + PANEL_SUMMARY_GAP

        mouse_pos = pygame.mouse.get_pos()
        rect = pygame.Rect(x, y, START_BUTTON_WIDTH, START_BUTTON_HEIGHT)
        color = START_BUTTON_HOVER_COLOR if rect.collidepoint(mouse_pos) else START_BUTTON_COLOR
        pygame.draw.rect(screen, color, rect, border_radius=6)
        label_surface = label_font.render("Start", True, PANEL_BUTTON_TEXT_COLOR)
        screen.blit(label_surface, label_surface.get_rect(center=rect.center))

        return [(rect, on_start_click)]

    def _draw_color_palette(self, screen: pygame.Surface, x: int, y: int, selected_color: TokenColorKind,
                             on_select_color) -> list[tuple[pygame.Rect, object]]:
        """Draws one swatch per `TokenColorKind`, in a row starting at `(x, y)`,
        with a heavier border around whichever one is `selected_color`. Each
        swatch's callback just reports its own color back to `on_select_color`
        -- the caller owns what "selected" actually means (`run()`'s own
        `selected_color` state), this method only renders the current value
        and reports clicks.
        """
        buttons = []
        swatch_x = x
        for color in TokenColorKind:
            rect = pygame.Rect(swatch_x, y, PALETTE_SWATCH_SIZE, PALETTE_SWATCH_SIZE)
            pygame.draw.rect(screen, TOKEN_COLORS[color], rect, border_radius=4)
            is_selected = color == selected_color
            border_color = PALETTE_SELECTED_BORDER_COLOR if is_selected else PALETTE_UNSELECTED_BORDER_COLOR
            pygame.draw.rect(screen, border_color, rect, width=3 if is_selected else 1, border_radius=4)
            buttons.append((rect, lambda c=color: on_select_color(c)))
            swatch_x += PALETTE_SWATCH_SIZE + PALETTE_SWATCH_GAP
        return buttons

    def _draw_machine_panel(self, screen: pygame.Surface, machines, unowned_token_count: int, font: pygame.font.Font,
                             label_font: pygame.font.Font, selected_color: TokenColorKind, on_select_color,
                             on_place_token) -> list[tuple[pygame.Rect, object]]:
        """Draws a side panel to the right of the viewport: a factory-wide
        summary line, a token-color palette, then each machine's live
        attributes and an optional row of buttons, one stacked block per
        machine. Machines are labeled by their own SysML part name (e.g.
        "Belt: cb1") -- `machine.name` (`PartSimulationModel`) holds the
        qualified name `Factory.instantiate_machine()` assigned it (see
        `PartInstantiation.evaluate()`, runtime.py); the leaf segment
        after the last `::` is what the model itself calls the part
        (`part cb1 : ...`), same split `PartInstantiation.evaluate()`
        already does for `part_def_name`. `drawer.panel_label` (e.g.
        "Belt") is kept as a kind prefix so the machine's type is still
        visible at a glance. placementCoordinate is deliberately omitted:
        it's already conveyed by the machine's drawn position in the
        viewport.

        The live attribute lines and button row are both delegated to each
        machine's own `MachineVisualization` drawer (`panel_lines()`/
        `panel_buttons()`, `fischertechnik_parts_visualization/generic.py`)
        instead of being hardcoded here -- this method used to assume every
        machine was a ConveyorBeltMachine (`machine.conveyorSensFeed`,
        `machine.pre_feed_position()`, ...), which would raise
        `AttributeError` the moment a different machine kind (e.g.
        VacuumGripperMachine) got registered.

        Returns the (rect, callback) pairs for every button just drawn
        (palette swatches and placement buttons alike), so the caller's event
        loop can hit-test all of them the same way, computed here in the same
        pass as the drawing so the clickable area can never drift out of sync
        with what's on screen.
        """
        panel_rect = pygame.Rect(PANEL_X, 0, PANEL_WIDTH, VIEWPORT_SIZE[1])
        pygame.draw.rect(screen, PANEL_BACKGROUND_COLOR, panel_rect)
        pygame.draw.line(screen, PANEL_DIVIDER_COLOR, (PANEL_X, 0), (PANEL_X, VIEWPORT_SIZE[1]), 2)

        mouse_pos = pygame.mouse.get_pos()
        x = PANEL_X + PANEL_LEFT_PADDING
        y = PANEL_TOP_PADDING

        screen.blit(font.render(f"Unowned tokens: {unowned_token_count}", True, PANEL_TEXT_COLOR), (x, y))
        y += PANEL_LINE_HEIGHT + PANEL_SUMMARY_GAP

        screen.blit(font.render("Token color to place:", True, PANEL_TEXT_COLOR), (x, y))
        y += PANEL_LINE_HEIGHT
        buttons = self._draw_color_palette(screen, x, y, selected_color, on_select_color)
        y += PALETTE_SWATCH_SIZE + PANEL_SUMMARY_GAP

        for machine in machines:
            drawer = self._drawers[type(machine)]
            part_name = machine.name.split("::")[-1]

            screen.blit(label_font.render(f"{drawer.panel_label}: {part_name}", True, PANEL_TEXT_COLOR), (x, y))
            y += PANEL_LINE_HEIGHT

            for line in drawer.panel_lines(machine):
                screen.blit(font.render(line, True, PANEL_TEXT_COLOR), (x, y))
                y += PANEL_LINE_HEIGHT

            button_row = drawer.panel_buttons(screen, x, y, font, mouse_pos, machine, on_place_token)
            buttons.extend(button_row)
            if button_row:
                y += PANEL_BUTTON_HEIGHT
            y += PANEL_MACHINE_GAP

        return buttons

    def _draw_viewport(self, screen: pygame.Surface, font: pygame.font.Font, factory) -> None:
        """The main factory-floor drawing (background, grid, every belt,
        every token) -- happens every frame regardless of whether the
        simulation has started, since belts/tokens already in `factory` are
        drawn even before "Start" (see `run()`'s docstring). Factored
        out so `run()`'s loop only needs to branch on `started` once
        per frame, not twice around this shared, `started`-independent work.

        The background fill is deliberately scoped to just the viewport rect
        (`VIEWPORT_SIZE`), not the whole window -- `screen` also includes the
        side panel (`WINDOW_SIZE = VIEWPORT_SIZE[0] + PANEL_WIDTH` wide), and
        `_draw_machine_panel()`/`_draw_start_panel()` already clear their own
        panel area independently (`PANEL_BACKGROUND_COLOR`). An unscoped fill
        here would wipe out whichever panel was drawn if this runs after it in
        a given frame -- scoping the fill means the two never touch each
        other's screen region, so which one runs first stops mattering.
        """
        screen.fill(BACKGROUND_COLOR, pygame.Rect(0, 0, VIEWPORT_SIZE[0], VIEWPORT_SIZE[1]))
        self._draw_grid(screen, font)
        self._draw_floor_boundary(screen)
        for machine in factory.machines:
            self._drawers[type(machine)].draw(screen, machine)
        for token in factory.tokens:
            self._draw_token(screen, token)

    def run(self, model, on_start=lambda: None, on_tick=lambda: None, tick_rate: int = 60) -> None:
        """Static-picture render loop: every frame, redraws every registered
        machine at its placementCoordinate. Redrawing from scratch each frame
        is required by pygame (unlike tkinter, it has no persistent canvas),
        even though nothing moves yet — Milestone 1 is static-only.

        `on_tick` runs right after `model.tick()`, once per frame, only once
        the simulation has started -- see main_lipvm_dtsimulation.py's
        `on_tick`, which publishes a fresh snapshot there (TODAYS-TASKS.md step
        2). Defaults to a no-op so callers with nothing to do after a tick
        (e.g. factory_simulation_demo.py) don't need to pass anything.

        Nothing runs until the user clicks "Start": `model.tick()` is
        skipped, and the panel shows `_draw_start_panel()` instead of the
        normal per-machine one (there's nothing to show yet -- `on_start`, not
        this method, is what actually populates `model.machines`). `started`
        flips permanently to True the moment that button fires; `on_start`
        itself (defined by the caller, see main_lipvm_dtsimulation.py) is
        responsible for whatever needs to happen exactly once at that point
        (the model's eager part-instantiation pass, releasing the interpreter
        thread, etc.) -- this method only decides what to draw/tick based on
        whether that's happened yet. Belts/tokens already in `model` are
        still drawn even before "Start" (`factory_simulation_demo.py` builds
        its belts synchronously up front and has nothing to gate, hence
        `on_start`'s no-op default) -- only `model.tick()` and the
        interpreter-driven case's part-instantiation are actually deferred.
        """
        pygame.init()
        screen = pygame.display.set_mode(WINDOW_SIZE)
        pygame.display.set_caption("Fischertechnik Factory")
        clock = pygame.time.Clock()
        font = pygame.font.SysFont(None, 18)
        label_font = pygame.font.SysFont(None, 20, bold=True)

        started = False
        selected_color = TokenColorKind.BLUE
        next_token_id = itertools.count(1)

        def handle_start():
            nonlocal started
            on_start()
            started = True

        def handle_select_color(color: TokenColorKind) -> None:
            nonlocal selected_color
            selected_color = color

        def handle_place_token(machine, position: FactoryCoordinate) -> None:
            token = Token(f"T{next(next_token_id)}", position, selected_color)
            model.spawn_token(token, machine)

        running = True
        buttons: list[tuple[pygame.Rect, object]] = []
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, callback in buttons:
                        if rect.collidepoint(event.pos):
                            callback()
                            break

            if started:
                model.tick()
                on_tick()
                unowned_token_count = len(model.tokens_on(None))
                buttons = self._draw_machine_panel(screen, model.machines, unowned_token_count, font, label_font,
                                                    selected_color, handle_select_color, handle_place_token)
            else:
                buttons = self._draw_start_panel(screen, font, label_font, handle_start)

            self._draw_viewport(screen, font, model)
            pygame.display.flip()
            clock.tick(tick_rate)

        pygame.quit()
