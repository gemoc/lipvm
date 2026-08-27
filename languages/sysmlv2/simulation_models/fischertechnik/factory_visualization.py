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

import math
import os
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")  # this file can get imported just for class discovery (see registry.py), not necessarily to actually render -- suppress pygame's own import-time banner so it doesn't pollute stdout for callers who never asked for it
import pygame

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import TokenColorKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import TICKS_PER_STEP_MIN, TICKS_PER_STEP_MAX
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts.conveyor_belt import CB_LENGTH, CB_WIDTH
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
BELT_WIDTH = CB_LENGTH * SCALE + 20

# Model-unit, cross-belt (perpendicular-to-travel) dimension -- purely a
# rendering size, unlike FEED_TO_SWAP_LENGTH/FULL_LENGTH (conveyor_belt.py), which
# also drive movement math. No simulation behavior depends on this value,
# so it lives here rather than in conveyor_belt.py.
BELT_HEIGHT = CB_WIDTH * SCALE


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

PANEL_SCROLLBAR_WIDTH = 8    # px, the draggable thumb/track's own width
PANEL_SCROLLBAR_MARGIN = 2   # px gap on each side of the scrollbar, both from the
                              # panel's content area and from the window's right edge
PANEL_SCROLLBAR_GUTTER = PANEL_SCROLLBAR_WIDTH + PANEL_SCROLLBAR_MARGIN * 2  # reserved
                              # strip to the right of PANEL_WIDTH -- kept separate from
                              # it so the scrollbar never overlaps the widest panel_lines()
                              # row the PANEL_WIDTH comment above sizes for
PANEL_TOTAL_WIDTH = PANEL_WIDTH + PANEL_SCROLLBAR_GUTTER

WINDOW_SIZE = (VIEWPORT_SIZE[0] + PANEL_TOTAL_WIDTH, VIEWPORT_SIZE[1])
BACKGROUND_COLOR = (255, 255, 255)

PANEL_X = VIEWPORT_SIZE[0]
PANEL_SCROLLBAR_TRACK_RECT = pygame.Rect(  # fixed for the window's lifetime -- only the
    PANEL_X + PANEL_WIDTH + PANEL_SCROLLBAR_MARGIN, 0,  # thumb's position/height within it
    PANEL_SCROLLBAR_WIDTH, VIEWPORT_SIZE[1])            # varies with content height/scroll
PANEL_BACKGROUND_COLOR = (245, 245, 245)
PANEL_DIVIDER_COLOR = (60, 60, 60)
PANEL_TEXT_COLOR = (20, 20, 20)
PANEL_LEFT_PADDING = 16
PANEL_TOP_PADDING = 16
PANEL_LINE_HEIGHT = 20
PANEL_MACHINE_GAP = 14           # extra vertical gap after each machine's block
PANEL_SUMMARY_GAP = 14           # extra vertical gap after the factory-wide summary line

PANEL_SCROLLBAR_TRACK_COLOR = (225, 225, 225)
PANEL_SCROLLBAR_THUMB_COLOR = (170, 170, 170)
PANEL_SCROLLBAR_THUMB_HOVER_COLOR = (130, 130, 130)
PANEL_SCROLLBAR_MIN_THUMB_HEIGHT = 24  # px floor so the thumb stays grabbable even
                                        # when there are enough machines that content
                                        # height dwarfs the panel's own VIEWPORT_SIZE[1]
PANEL_SCROLL_WHEEL_STEP = 40           # px scrolled per mouse-wheel notch

PANEL_BUTTON_TEXT_COLOR = (20, 20, 20)

PANEL_BUTTON_WIDTH = 100         # wide enough for the longest current label, "Random Emit"
                                  # (TokenProducerVisualization), at ~78px rendered plus padding --
                                  # the only remaining panel_buttons() user now that CB/VGR no
                                  # longer have any
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

INPUT_FIELD_WIDTH = 70
INPUT_FIELD_HEIGHT = 22
INPUT_FIELD_LABEL_WIDTH = 90     # fixed label column before each box -- avoids measuring each label's own text width just to lay things out
INPUT_FIELD_GROUP_GAP = 20       # horizontal gap between one label+box pair and the next, in the same row
INPUT_FIELD_ROW_GAP = 8          # vertical gap between input-field rows
INPUT_FIELD_BACKGROUND_COLOR = (255, 255, 255)
INPUT_FIELD_BORDER_COLOR = (150, 150, 150)
INPUT_FIELD_FOCUSED_BORDER_COLOR = (90, 90, 220)  # matches SPEED_SLIDER_HANDLE_COLOR -- same "this is the live control" accent
INPUT_FIELD_TEXT_COLOR = (20, 20, 20)

SPEED_SLIDER_WIDTH = 220         # px, track width -- comfortably inside PANEL_WIDTH's usable area
SPEED_SLIDER_TRACK_HEIGHT = 6    # px
SPEED_SLIDER_HANDLE_RADIUS = 8   # px
SPEED_SLIDER_HIT_PADDING = 6     # px, grown around the visible track/handle so dragging isn't pixel-perfect
SPEED_SLIDER_TRACK_COLOR = (200, 200, 200)
SPEED_SLIDER_HANDLE_COLOR = (90, 90, 220)

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


def _panel_scroll_offset_from_y(mouse_y: int, track_rect: pygame.Rect, thumb_height: int, max_scroll: int) -> int:
    """Inverse of the thumb-position math in `_draw_machine_panel`'s
    scrollbar -- given a mouse y position (from a click or drag on the
    scrollbar track), returns the panel scroll_offset it corresponds to.
    Plays the same role for the scrollbar that `_speed_slider_value_from_x`
    plays for the speed slider: `run()`'s event loop owns the drag state
    across frames, this just maps a position to a value. Positions the
    thumb's *center* under the mouse rather than its top, so a click
    anywhere on the track jumps the content by roughly that click's
    proportion down the panel instead of snapping the thumb's far edge
    there.
    """
    usable = track_rect.height - thumb_height
    if usable <= 0 or max_scroll <= 0:
        return 0
    frac = (mouse_y - track_rect.top - thumb_height / 2) / usable
    frac = max(0.0, min(1.0, frac))
    return round(frac * max_scroll)


def _speed_slider_value_from_x(mouse_x: int, track_rect: pygame.Rect) -> int:
    """Inverse of the handle-position math in `_draw_speed_slider` --
    given a mouse x position (from a click or drag over the slider),
    returns the TICKS_PER_STEP value it corresponds to. Deliberately
    inverted (left = TICKS_PER_STEP_MAX/slowest, right =
    TICKS_PER_STEP_MIN/fastest): dragging right to go faster matches the
    usual "more/right" intuition better than a raw ascending
    left-to-right mapping would, given a lower TICKS_PER_STEP means a
    *faster* simulation.
    """
    frac = (mouse_x - track_rect.left) / track_rect.width
    frac = max(0.0, min(1.0, frac))
    value = TICKS_PER_STEP_MAX - frac * (TICKS_PER_STEP_MAX - TICKS_PER_STEP_MIN)
    return round(value)


def _is_valid_numeric_input_char(char: str, current_text: str) -> bool:
    """Whether typing `char` next is legal for a float-typed input field
    already containing `current_text` -- digits always are; '.' only if
    `current_text` doesn't already have one; '-' only as the very first
    character (a bare `float("...")` call would reject a stray/repeated
    '-' or a second '.' anyway, but rejecting them here means the field
    never displays something that can't parse in the first place).
    """
    if char.isdigit():
        return True
    if char == "." and "." not in current_text:
        return True
    if char == "-" and current_text == "":
        return True
    return False


def draw_color_palette(screen: pygame.Surface, x: int, y: int, selected_color: TokenColorKind,
                        on_select_color) -> list[tuple[pygame.Rect, object]]:
    """Draws one swatch per `TokenColorKind`, in a row starting at `(x, y)`,
    with a heavier border around whichever one is `selected_color`. Each
    swatch's callback just reports its own color back to `on_select_color`
    -- the caller owns what "selected" actually means, this function only
    renders the current value and reports clicks.

    Module-level (not a `FischertechnikVisualization` method) so any
    per-machine `MachineVisualization` drawer can call it directly --
    currently only `TokenProducerVisualization`, whose "Emit Token"
    button needs a color to emit, same "import a shared helper from here"
    pattern `_to_screen`/`SCALE`/etc. already use across
    fischertechnik_parts_visualization/*.py.
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

class FischertechnikVisualization(SimulationVisualization):
    """Fischertechnik's SimulationVisualization (generic.py). `run()` is
    the only method ever called from outside this class -- every other
    method below is a private drawing helper, previously a module-level
    function, moved here so the whole rendering surface lives on one
    class instead of being split between free functions and a thin
    wrapper around them.

    `run()`'s own local state (`started`/`selected_color`)
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
        panel_rect = pygame.Rect(PANEL_X, 0, PANEL_TOTAL_WIDTH, VIEWPORT_SIZE[1])
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

    def _draw_speed_slider(self, screen: pygame.Surface, x: int, y: int, font: pygame.font.Font,
                            ticks_per_step: int) -> pygame.Rect:
        """Draws a horizontal "Speed" slider: a label showing the current
        TICKS_PER_STEP value, a track, and a draggable handle positioned
        by it (via `_speed_slider_value_from_x`'s inverse mapping).
        Doesn't take a callback or do any hit-testing itself -- `run()`'s
        event loop owns dragging state (click-and-hold spans multiple
        frames, unlike the one-shot buttons `panel_buttons()`/
        `draw_color_palette()` return), so this method only draws and
        hands back the track's hit-rect (padded by
        SPEED_SLIDER_HIT_PADDING so a drag doesn't need pixel-perfect
        aim) for `run()` to test clicks/drags against.
        """
        label = font.render(f"Speed (TICKS_PER_STEP={ticks_per_step}):", True, PANEL_TEXT_COLOR)
        screen.blit(label, (x, y))

        track_y = y + PANEL_LINE_HEIGHT + SPEED_SLIDER_HANDLE_RADIUS
        track_rect = pygame.Rect(x, track_y - SPEED_SLIDER_TRACK_HEIGHT // 2, SPEED_SLIDER_WIDTH, SPEED_SLIDER_TRACK_HEIGHT)
        pygame.draw.rect(screen, SPEED_SLIDER_TRACK_COLOR, track_rect, border_radius=SPEED_SLIDER_TRACK_HEIGHT // 2)

        frac = (TICKS_PER_STEP_MAX - ticks_per_step) / (TICKS_PER_STEP_MAX - TICKS_PER_STEP_MIN)
        frac = max(0.0, min(1.0, frac))
        handle_x = track_rect.left + frac * track_rect.width
        pygame.draw.circle(screen, SPEED_SLIDER_HANDLE_COLOR, (int(handle_x), track_y), SPEED_SLIDER_HANDLE_RADIUS)

        return track_rect.inflate(SPEED_SLIDER_HIT_PADDING * 2, SPEED_SLIDER_HANDLE_RADIUS * 2)

    def _draw_machine_panel(self, screen: pygame.Surface, machines, unowned_token_count: int, font: pygame.font.Font,
                             label_font: pygame.font.Font, selected_color: TokenColorKind, on_select_color,
                             ticks_per_step: int, field_values: dict, focused_field, scroll_offset: int
                             ) -> tuple[list[tuple[pygame.Rect, object]], pygame.Rect, list[tuple[str, pygame.Rect]], int, pygame.Rect | None]:
        """Draws a side panel to the right of the viewport: a factory-wide
        summary line, then each machine's live attributes and an optional
        row of buttons, one stacked block per machine. Machines are
        labeled by their own SysML part name (e.g. "Belt: cb1") --
        `machine.name` (`PartSimulationModel`) holds the qualified name
        `Factory.instantiate_machine()` assigned it (see
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
        VacuumGripperMachine) got registered. `selected_color`/
        `on_select_color` are threaded down to each drawer's own
        `panel_buttons()` rather than drawing a shared palette here --
        currently only `TokenProducerVisualization` uses them (its own
        color picker, scoped right above its Emit Token/Random Emit
        buttons, drawn via `draw_color_palette()`).

        Returns the (rect, callback) pairs for every button just drawn,
        the speed slider's own hit-rect, every input field's (field_key,
        hit_rect) pair (see panel_input_fields(), generic.py), the
        content's own max scroll offset, and the scrollbar thumb's hit-rect
        (or None when nothing overflows and no scrollbar was drawn) -- so
        the caller's event loop can hit-test all of them the same way,
        computed here in the same pass as the drawing so the clickable
        area can never drift out of sync with what's on screen.

        `scroll_offset` shifts every row up by that many pixels before
        drawing (rather than scrolling a pre-rendered surface), so hit-test
        rects for buttons/fields/the slider come out already in real
        on-screen coordinates -- no separate translation step needed by
        `run()`. Content is clipped to `panel_rect`'s vertical extent
        (`screen.set_clip`) while scrolled, so rows pushed above y=0 or
        below the panel's bottom by the offset don't leak into the
        viewport above/below it; the clip is lifted again before the
        scrollbar itself is drawn, since that lives in its own gutter
        beside `panel_rect` and doesn't need it.
        """
        panel_rect = pygame.Rect(PANEL_X, 0, PANEL_TOTAL_WIDTH, VIEWPORT_SIZE[1])
        pygame.draw.rect(screen, PANEL_BACKGROUND_COLOR, panel_rect)
        pygame.draw.line(screen, PANEL_DIVIDER_COLOR, (PANEL_X, 0), (PANEL_X, VIEWPORT_SIZE[1]), 2)

        mouse_pos = pygame.mouse.get_pos()
        x = PANEL_X + PANEL_LEFT_PADDING
        y = PANEL_TOP_PADDING - scroll_offset
        content_top = y

        content_clip_rect = pygame.Rect(PANEL_X, 0, PANEL_WIDTH, VIEWPORT_SIZE[1])
        screen.set_clip(content_clip_rect)

        screen.blit(font.render(f"Unowned tokens: {unowned_token_count}", True, PANEL_TEXT_COLOR), (x, y))
        y += PANEL_LINE_HEIGHT + PANEL_SUMMARY_GAP

        speed_slider_rect = self._draw_speed_slider(screen, x, y, font, ticks_per_step)
        y += PANEL_LINE_HEIGHT + SPEED_SLIDER_HANDLE_RADIUS * 2 + PANEL_SUMMARY_GAP

        buttons: list[tuple[pygame.Rect, object]] = []
        input_fields: list[tuple[str, pygame.Rect]] = []
        for machine in machines:
            drawer = self._drawers[type(machine)]
            part_name = machine.name.split("::")[-1]

            screen.blit(label_font.render(f"{drawer.panel_label}: {part_name}", True, PANEL_TEXT_COLOR), (x, y))
            y += PANEL_LINE_HEIGHT

            for line in drawer.panel_lines(machine):
                screen.blit(font.render(line, True, PANEL_TEXT_COLOR), (x, y))
                y += PANEL_LINE_HEIGHT

            field_row = drawer.panel_input_fields(screen, x, y, font, machine, field_values, focused_field)
            input_fields.extend(field_row)
            if field_row:
                y = max(rect.bottom for _, rect in field_row) + INPUT_FIELD_ROW_GAP

            button_row = drawer.panel_buttons(screen, x, y, font, mouse_pos, machine, selected_color, on_select_color, field_values)
            buttons.extend(button_row)
            if button_row:
                # Derived from the actual drawn rects' bottoms (like
                # field_row's own height above), not a fixed
                # PANEL_BUTTON_HEIGHT constant -- lets a drawer lay out
                # more than one row (e.g. TokenProducerVisualization's own
                # color picker above its action buttons) without this
                # method needing to know its layout in advance.
                y = max(rect.bottom for rect, _ in button_row)
            y += PANEL_MACHINE_GAP

        screen.set_clip(None)

        # content_height is what the layout above would have measured with
        # scroll_offset == 0 -- back it out from the offset y actually
        # started/ended at, rather than re-running the layout, so this stays
        # a single drawing pass like every other method here.
        content_height = round(y - content_top)  # some drawer's panel_input_fields()/
                                                   # panel_buttons() can hand back a
                                                   # sub-pixel rect.bottom -- round once
                                                   # here so max_scroll/thumb math below
                                                   # stays in whole pixels throughout
        max_scroll = max(0, content_height - VIEWPORT_SIZE[1])

        thumb_rect = None
        if max_scroll > 0:
            track_rect = PANEL_SCROLLBAR_TRACK_RECT
            pygame.draw.rect(screen, PANEL_SCROLLBAR_TRACK_COLOR, track_rect)
            thumb_height = max(PANEL_SCROLLBAR_MIN_THUMB_HEIGHT,
                                round(track_rect.height * VIEWPORT_SIZE[1] / content_height))
            thumb_height = min(thumb_height, track_rect.height)
            thumb_y = track_rect.top + round(scroll_offset / max_scroll * (track_rect.height - thumb_height))
            thumb_rect = pygame.Rect(track_rect.x, thumb_y, track_rect.width, thumb_height)
            thumb_color = PANEL_SCROLLBAR_THUMB_HOVER_COLOR if thumb_rect.collidepoint(mouse_pos) else PANEL_SCROLLBAR_THUMB_COLOR
            pygame.draw.rect(screen, thumb_color, thumb_rect, border_radius=PANEL_SCROLLBAR_WIDTH // 2)

        return buttons, speed_slider_rect, input_fields, max_scroll, thumb_rect

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

        def handle_start():
            nonlocal started
            on_start()
            started = True

        def handle_select_color(color: TokenColorKind) -> None:
            nonlocal selected_color
            selected_color = color

        running = True
        dragging_speed_slider = False
        dragging_scrollbar = False
        buttons: list[tuple[pygame.Rect, object]] = []
        speed_slider_rect: pygame.Rect | None = None
        input_fields: list[tuple[str, pygame.Rect]] = []
        field_values: dict[str, str] = {}
        focused_field: str | None = None
        panel_scroll_offset = 0
        panel_max_scroll = 0            # from last frame's _draw_machine_panel -- see its
        scrollbar_thumb_rect = None     # docstring for why a one-frame lag here is fine,
                                         # same as buttons/speed_slider_rect/input_fields already are
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if scrollbar_thumb_rect is not None and scrollbar_thumb_rect.collidepoint(event.pos):
                        dragging_scrollbar = True
                        panel_scroll_offset = _panel_scroll_offset_from_y(
                            event.pos[1], PANEL_SCROLLBAR_TRACK_RECT, scrollbar_thumb_rect.height, panel_max_scroll)
                    elif panel_max_scroll > 0 and PANEL_SCROLLBAR_TRACK_RECT.collidepoint(event.pos):
                        dragging_scrollbar = True
                        thumb_height = scrollbar_thumb_rect.height if scrollbar_thumb_rect is not None else PANEL_SCROLLBAR_MIN_THUMB_HEIGHT
                        panel_scroll_offset = _panel_scroll_offset_from_y(
                            event.pos[1], PANEL_SCROLLBAR_TRACK_RECT, thumb_height, panel_max_scroll)
                    elif speed_slider_rect is not None and speed_slider_rect.collidepoint(event.pos):
                        dragging_speed_slider = True
                        model.ticks_per_step = _speed_slider_value_from_x(event.pos[0], speed_slider_rect)
                    elif any(rect.collidepoint(event.pos) for _, rect in input_fields):
                        focused_field = next(key for key, rect in input_fields if rect.collidepoint(event.pos))
                    else:
                        focused_field = None
                        for rect, callback in buttons:
                            if rect.collidepoint(event.pos):
                                callback()
                                break
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    dragging_speed_slider = False
                    dragging_scrollbar = False
                elif event.type == pygame.MOUSEMOTION and dragging_speed_slider:
                    model.ticks_per_step = _speed_slider_value_from_x(event.pos[0], speed_slider_rect)
                elif event.type == pygame.MOUSEMOTION and dragging_scrollbar:
                    thumb_height = scrollbar_thumb_rect.height if scrollbar_thumb_rect is not None else PANEL_SCROLLBAR_MIN_THUMB_HEIGHT
                    panel_scroll_offset = _panel_scroll_offset_from_y(
                        event.pos[1], PANEL_SCROLLBAR_TRACK_RECT, thumb_height, panel_max_scroll)
                elif event.type == pygame.MOUSEWHEEL and pygame.mouse.get_pos()[0] >= PANEL_X:
                    panel_scroll_offset = max(0, min(panel_max_scroll, panel_scroll_offset - event.y * PANEL_SCROLL_WHEEL_STEP))
                elif event.type == pygame.KEYDOWN and focused_field is not None:
                    current = field_values.get(focused_field, "")
                    if event.key == pygame.K_BACKSPACE:
                        field_values[focused_field] = current[:-1]
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                        focused_field = None
                    elif event.unicode and _is_valid_numeric_input_char(event.unicode, current):
                        field_values[focused_field] = current + event.unicode

            if started:
                model.tick()
                on_tick()
                unowned_token_count = len(model.tokens_on(None))
                buttons, speed_slider_rect, input_fields, panel_max_scroll, scrollbar_thumb_rect = self._draw_machine_panel(
                    screen, model.machines, unowned_token_count, font, label_font,
                    selected_color, handle_select_color, model.ticks_per_step,
                    field_values, focused_field, panel_scroll_offset)
                panel_scroll_offset = min(panel_scroll_offset, panel_max_scroll)
            else:
                buttons = self._draw_start_panel(screen, font, label_font, handle_start)
                input_fields = []
                speed_slider_rect = None
                panel_scroll_offset = 0
                panel_max_scroll = 0
                scrollbar_thumb_rect = None

            self._draw_viewport(screen, font, model)
            pygame.display.flip()
            clock.tick(tick_rate)

        pygame.quit()
