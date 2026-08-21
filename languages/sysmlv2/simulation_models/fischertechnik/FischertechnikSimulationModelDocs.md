# Fischertechnik Factory Visualization Documentation

How model coordinates (`FactoryCoordinate.x`/`.y`, e.g. a part's
`placementCoordinate`) map onto the rendered viewport.

Source: `factory_visualization.py`

## The factory floor: 0 to 40 on both axes

The floor is a `MODEL_RANGE x MODEL_RANGE` square (`MODEL_RANGE = 40`).
**Model `(0, 0)` is the floor's bottom-left corner; `(40, 40)` is its
top-right corner** — drawn on screen as a visible bordered rect
(`_draw_floor_boundary`), so the corner isn't just implied by where the
grid's axis lines cross, it's an actual outline.

```python
SCALE = 20                       # pixels per model unit
MODEL_RANGE = 40                 # factory floor spans model coordinates 0..MODEL_RANGE on both x and y
FEED_TO_SWAP_LENGTH = 4          # model units, distance between a belt's feed and swap sensors (conveyor_belt.py)
FULL_LENGTH = 6                  # model units, total ownable extent incl. one overshoot step past each sensor (conveyor_belt.py)

BELT_WIDTH = FULL_LENGTH * SCALE + 20   # = 140 (7 model units)
BELT_CROSS_WIDTH = 2             # model units, cross-belt (perpendicular-to-travel) dimension
BELT_HEIGHT = BELT_CROSS_WIDTH * SCALE                              # = 40 (2 model units)
```

`BELT_WIDTH` (long axis, along travel direction) and `BELT_HEIGHT` (short
axis, across the belt) are both now expressed as a model-unit quantity
times `SCALE` — no bare pixel numbers. `BELT_HEIGHT` is purely a rendering
size (unlike `FEED_TO_SWAP_LENGTH`/`FULL_LENGTH`, which also drive movement
math in `fischertechnik_parts/conveyor_belt.py`) — no simulation behavior depends on it, so
`BELT_CROSS_WIDTH` lives in `factory_visualization.py`, not `fischertechnik_parts/conveyor_belt.py`.

`FEED_TO_SWAP_LENGTH`/`FULL_LENGTH` (`fischertechnik_parts/conveyor_belt.py`) replaced the older
`HALF_LENGTH`/`OVERSHOOT_TOLERANCE` pair — same values, expressed as two
full lengths instead of a half-length plus a tolerance to add to it:
`FEED_TO_SWAP_LENGTH` is the distance between the feed and swap sensors a
token actually rides across (`feed_position()`/`swap_position()`, each
`FEED_TO_SWAP_LENGTH / 2` from center); `FULL_LENGTH` is the belt's total
ownable extent, including one overshoot step past each sensor
(`pre_feed_position()`/`post_swap_position()`/the disown check in
`advance()`, each `FULL_LENGTH / 2` from center).

### Belt footprint, in model units

| dimension | model units | pixels | source |
|---|---|---|---|
| length (along travel, `BELT_WIDTH`) | 7 | 140 | `FULL_LENGTH` (= 6, functional) `+ 1` (cosmetic pad, not tied to any model constant) |
| cross-width (across the belt, `BELT_HEIGHT`) | 2 | 40 | `BELT_CROSS_WIDTH` |

A belt therefore occupies a **7 × 2 model-unit** footprint (before rotation),
centered on its `placementCoordinate` — i.e. it reaches 3.5 model units
either side of center along its length, and 1 model unit either side across
it. On the 40 × 40 floor, that means a belt's *center* should generally stay
within roughly `[3.5, 36.5]` on its long axis and `[1, 39]` on its cross
axis to keep the whole belt inside the floor boundary itself (separate from
the canvas-overhang margin below, which exists precisely so going slightly
past that still doesn't clip).

`FactoryCoordinate` (`custom_attribute.py`) itself has no validation or
clamping on `x`/`y` — any float is accepted. A `placementCoordinate` outside
0–40 still exists as a value; it just renders outside the floor's drawn
boundary (still visible in the surrounding margin, up to a point — see
below).

## Computing a belt's feed/swap (and overshoot) positions

Given a belt's `placementCoordinate = (x₀, y₀, θ)`, its sensor and overshoot
positions are deterministic — no need to run the simulation to find them.
This is exactly `_end_position()` in `fischertechnik_parts/conveyor_belt.py`: rotate a local-x offset by
`θ` around the belt's center, add to `(x₀, y₀)`, round to the nearest grid
cell.

```
feed       = ( round(x₀ − 2·cos θ), round(y₀ − 2·sin θ) )   # FEED_TO_SWAP_LENGTH / 2 = 2
swap       = ( round(x₀ + 2·cos θ), round(y₀ + 2·sin θ) )
pre_feed   = ( round(x₀ − 3·cos θ), round(y₀ − 3·sin θ) )   # FULL_LENGTH / 2 = 3
post_swap  = ( round(x₀ + 3·cos θ), round(y₀ + 3·sin θ) )
```

`θ` is in degrees, converted to radians before applying `cos`/`sin`. This is
standard math convention (counterclockwise), computed in model space --
*before* the visualization's y-flip for screen rendering (see "Screen
mapping" below), so don't derive it by eyeballing the rendered image.

For the four cardinal rotations belts are actually placed at (0/90/180/270°),
this resolves to exact integers, no rounding error:

| `degrees` | feed | swap | pre_feed | post_swap |
|---|---|---|---|---|
| `0`   | `(x₀ − 2, y₀)` | `(x₀ + 2, y₀)` | `(x₀ − 3, y₀)` | `(x₀ + 3, y₀)` |
| `90`  | `(x₀, y₀ − 2)` | `(x₀, y₀ + 2)` | `(x₀, y₀ − 3)` | `(x₀, y₀ + 3)` |
| `180` | `(x₀ + 2, y₀)` | `(x₀ − 2, y₀)` | `(x₀ + 3, y₀)` | `(x₀ − 3, y₀)` |
| `270` | `(x₀, y₀ + 2)` | `(x₀, y₀ − 2)` | `(x₀, y₀ + 3)` | `(x₀, y₀ − 3)` |

Useful for placing a part that services this belt (e.g. a gripper) without
running the simulation first: target `swap` to pick a token off the belt,
`feed` to place one on, `pre_feed`/`post_swap` to reach the one-step
overshoot boundary rather than the sensor itself.

**Worked example** — belt at `(x₀=10.0, y₀=0.0, θ=0.0)`:
`feed = (8, 0)`, `swap = (12, 0)`, `pre_feed = (7, 0)`, `post_swap = (13, 0)`.

## Why there's a margin around the floor, and why it doesn't affect (0, 0)

A belt's `placementCoordinate` is its *center*, not a corner. A belt
centered exactly at `x=0` extends `BELT_WIDTH / 2` px to the left of that
point — if the canvas ended exactly at the floor edge, that half would be
clipped. Belts can also be rotated (0/90/180/270 degrees), so the same
overhang risk applies to `BELT_HEIGHT` on the y-axis too.

`_floor_layout()` solves this by reserving a uniform pixel margin *outside*
the floor rect, on all four sides, sized to the belt's largest dimension:

```python
def _floor_layout(model_range, scale, belt_width, belt_height):
    margin = max(belt_width, belt_height) // 2      # = 70 px, with today's belt size
    size = int(model_range * scale) + 2 * margin
    return (size, size), (margin, size - margin)     # -> VIEWPORT_SIZE, ORIGIN

VIEWPORT_SIZE, ORIGIN = _floor_layout(MODEL_RANGE, SCALE, BELT_WIDTH, BELT_HEIGHT)
# VIEWPORT_SIZE = (940, 940)
# ORIGIN        = (70, 870)
```

This margin is pure canvas padding for overhang — it is **not** part of the
model-coordinate range. A modeler writing `placementCoordinate` values never
sees or accounts for it: `(0, 0)` still means "the corner," full stop. If
belt dimensions ever change, the margin (and therefore `VIEWPORT_SIZE`)
recomputes automatically — nothing about the 0–40 floor range needs to
change with it.

## Screen mapping

```python
def _to_screen(coord: FactoryCoordinate) -> tuple[int, int]:
    px = ORIGIN[0] + coord.x * SCALE
    py = ORIGIN[1] - coord.y * SCALE   # y is flipped: pygame's screen y grows downward
    return int(px), int(py)
```

With today's constants:

| model coordinate | screen pixel |
|---|---|
| `(0, 0)` (floor's bottom-left corner) | `(70, 870)` |
| `(40, 40)` (floor's top-right corner) | `(870, 70)` |
| `(40, 0)` (bottom-right corner) | `(870, 870)` |
| `(0, 40)` (top-left corner) | `(70, 70)` |

The 70px gap between those pixel values and the actual canvas edges
(`0`/`940`) is the overhang margin described above.

Note `VIEWPORT_SIZE[0]` (`940`) is the boundary of the drawing area, not the
full pygame window — the side panel (`PANEL_WIDTH = 300`) starts immediately
after it (`PANEL_X = VIEWPORT_SIZE[0]`), so it's not available for placing
parts.

## Grid overlay

A reference grid is drawn every `GRID_STEP = 5` model units (`_draw_grid`),
labeled with the model coordinate each line represents, with the x=0/y=0
axis lines drawn heavier — these should align with the floor boundary's
bottom-left corner. Use the grid to visually cross-check a
`placementCoordinate` before committing to it in a model.

## Movement speed: TICKS_PER_STEP

How far a token moves per model-unit step is fixed (`cb_step_position()`,
`movement_computation_model.py`, always one model-grid unit). How *often*
that step actually happens — the belt's visible speed — is controlled
separately, in `factory.py`:

```python
# One visible hop every this many Factory.tick() calls -- 0.5s at the
# render loop's default 60fps (FactoryVisualization.run()'s tick_rate).
TICKS_PER_STEP = 30
```

`Factory.tick()` calls `machine.advance()` for a given belt only once every
`TICKS_PER_STEP` calls to `Factory.tick()` (via `StepPacer`,
`step_pacer.py`) — not every tick. `ConveyorBeltMachine.advance()` itself
has no timing/pacing logic of its own; whenever it *is* called, it just
moves owned tokens exactly one model-grid unit and checks its command's
stop condition. So:

- **To change belt speed**: tune `TICKS_PER_STEP` in `factory.py`.
- **To change step size**: tune `cb_step_position()` in
  `movement_computation_model.py`.

These are independent knobs — `Factory` decides *when* a belt is allowed to
move, `advance()` decides what one such move does.
