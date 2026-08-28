import pygame

from languages.sysmlv2.simulation_models.fischertechnik.enums import TokenColorKind
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts.sorting_line import (
    SortingLineMachine, SL_LENGTH, SL_WIDTH, BELT_WIDTH as SL_BELT_WIDTH,
    SORTED_TOKEN_PLATFORM_WIDTH,
)
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts_visualization.generic import MachineVisualization
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import (
    SCALE, _to_screen, TOKEN_COLORS, TOKEN_OUTLINE_COLOR,
    BELT_SURFACE_COLOR, BELT_TREAD_COLOR, FEED_COLOR, TREAD_SPACING, ROLLER_BAND_WIDTH,
)

SL_FRAME_COLOR = (90, 90, 90)        # housing outline
SL_HOUSING_COLOR = (215, 215, 215)   # housing fill -- lighter than the belt strip so the two read as separate parts
PISTON_COLOR = (110, 110, 110)       # the pusher itself is undyed; only the platform beneath it is colored per-token

# Rod's own on-screen thickness -- thick enough to read as a mechanical
# part, narrow enough that the colored platform underneath stays visible on
# either side of it.
PISTON_ROD_WIDTH_PX = 12

# Composite surface sizing: kept symmetric about the housing's own center
# so pygame.transform.rotate's pivot lands on placementCoordinate, even
# though the sort platforms only extend past the housing on one side --
# same reasoning TokenDepoVisualization's _HALF_SPAN comment gives for
# TokenDepoMachine's one-sided receiver.
_HALF_SPAN_Y = SL_WIDTH / 2 + SORTED_TOKEN_PLATFORM_WIDTH
SORTING_LINE_SURFACE_WIDTH = int(SL_LENGTH * SCALE) + 20
SORTING_LINE_SURFACE_HEIGHT = int(2 * _HALF_SPAN_Y * SCALE) + 20

# SL_LENGTH split into four equal zones along the belt: the entry sensor,
# then one ejector station per TokenColorKind (BLUE/WHITE/RED, same order
# as the sensor_SL_* attributes and SLMessages) -- each sensor location
# gets an equal quarter of the line's own length as its own proper area,
# rather than being sized off whatever room happened to be left over.
_ZONE_LENGTH = SL_LENGTH / 4
_ZONE_OFFSETS = [-SL_LENGTH / 2 + _ZONE_LENGTH * (i + 0.5) for i in range(4)]
_IN_SENSOR_OFFSET = _ZONE_OFFSETS[0]
_STATION_OFFSETS = _ZONE_OFFSETS[1:]

# Drawn width for each zone's own element (sensor band or platform/piston):
# a fixed pixel gap narrower than the zone itself, so the four zones still
# read as separate areas instead of touching edge to edge.
_ZONE_GAP_PX = 8
_ZONE_SPAN_PX = int(_ZONE_LENGTH * SCALE) - _ZONE_GAP_PX


class SortingLineVisualization(MachineVisualization):
    """Draws a SortingLineMachine from directly above: the housing
    (SL_LENGTH x SL_WIDTH), a center conveyor strip running its full
    length (styled like ConveyorBeltVisualization's own belt surface, for
    visual consistency with the machine it's built from), a band marking
    the inbound sensor near the entrance, and one colored sort platform +
    piston rod pair per TokenColorKind -- all ejecting toward the same
    side (the surface's top edge in this class's own unrotated,
    pre-rotation frame) -- the mental model being a token rides the center
    belt and, color-sensor by color-sensor, gets pushed off into whichever
    platform matches it.

    The piston is drawn as a rod running the full push-axis span, from the
    belt's own edge out to the platform's outer tip -- i.e. across the
    platform, not tucked into the housing/platform gap the way an earlier
    version of this drawing had it -- since that's the pusher's actual
    reach: it has to cross the whole platform to shove a token clear of
    the housing. Drawn after (on top of) the platform fill so the platform
    stays visible as color on either side of the rod.

    Each of the four sensor locations (entry, blue, white, red) gets an
    equal quarter of SL_LENGTH as its own zone (_ZONE_LENGTH/_ZONE_OFFSETS)
    -- a platform/piston's span *along* the belt is that zone's width, not
    PISTON_WIDTH (not cross-referenced by anything else yet, so free to
    pick here). SORTED_TOKEN_PLATFORM_WIDTH is still how far each platform
    extends *out* past the housing's edge. If either stops matching the
    real device, only the numbers above this class need to change.

    The entry sensor is the one exception: drawn at conveyor-belt scale
    (ROLLER_BAND_WIDTH, same as ConveyorBeltVisualization's own FEED/SWAP
    bands) rather than filling its whole zone, since it's a point sensor,
    not an ejector needing a platform. The rest of its zone is left as
    plain belt -- a transport stretch a token rides over without belonging
    to any sensor, distinct from the three color stations that each claim
    their full zone.

    Static picture only -- matches this class's own scope (eject()/stop()
    are still stubs in SortingLineMachine): no ejection animation, no
    reading of sensor_SL_* state to highlight anything yet. Composited on
    one local, unrotated surface first, then rotated as a whole and
    blitted centered on placementCoordinate -- same pattern
    ConveyorBeltVisualization/TokenDepoVisualization already use.
    """

    machine_type = SortingLineMachine
    panel_label = "Sorting Line"

    def panel_lines(self, machine: SortingLineMachine) -> list[str]:
        return [
            f"sensor_SL_in: {machine.sensor_SL_in}",
            f"sensor_SL_blue: {machine.sensor_SL_blue}",
            f"sensor_SL_white: {machine.sensor_SL_white}",
            f"sensor_SL_red: {machine.sensor_SL_red}",
        ]

    def draw(self, screen: pygame.Surface, machine: SortingLineMachine) -> None:
        surface = pygame.Surface((SORTING_LINE_SURFACE_WIDTH, SORTING_LINE_SURFACE_HEIGHT), pygame.SRCALPHA)
        center = surface.get_rect().center

        housing_rect = pygame.Rect(0, 0, int(SL_LENGTH * SCALE), int(SL_WIDTH * SCALE))
        housing_rect.center = center
        pygame.draw.rect(surface, SL_HOUSING_COLOR, housing_rect, border_radius=6)
        pygame.draw.rect(surface, SL_FRAME_COLOR, housing_rect, width=2, border_radius=6)

        belt_rect = pygame.Rect(0, 0, int(SL_LENGTH * SCALE), int(SL_BELT_WIDTH * SCALE))
        belt_rect.center = center
        pygame.draw.rect(surface, BELT_SURFACE_COLOR, belt_rect, border_radius=3)

        previous_clip = surface.get_clip()
        surface.set_clip(belt_rect)
        for x in range(belt_rect.left, belt_rect.right, TREAD_SPACING):
            pygame.draw.line(surface, BELT_TREAD_COLOR, (x, belt_rect.top), (x, belt_rect.bottom), 2)
        surface.set_clip(previous_clip)

        # Sized like a conveyor belt's own sensor band (ROLLER_BAND_WIDTH),
        # not the full width of its zone -- the rest of that zone is left as
        # plain belt, a transport stretch that isn't owned by any sensor.
        in_sensor_rect = pygame.Rect(0, 0, ROLLER_BAND_WIDTH, belt_rect.height)
        in_sensor_rect.center = (center[0] + int(_IN_SENSOR_OFFSET * SCALE), center[1])
        pygame.draw.rect(surface, FEED_COLOR, in_sensor_rect)

        for color, offset in zip(TokenColorKind, _STATION_OFFSETS):
            station_x = center[0] + int(offset * SCALE)

            platform_rect = pygame.Rect(0, 0, _ZONE_SPAN_PX, int(SORTED_TOKEN_PLATFORM_WIDTH * SCALE))
            platform_rect.midbottom = (station_x, housing_rect.top)
            pygame.draw.rect(surface, TOKEN_COLORS[color], platform_rect, border_radius=3)
            pygame.draw.rect(surface, TOKEN_OUTLINE_COLOR, platform_rect, width=2, border_radius=3)

            # Spans from the belt's own edge (near end) to the platform's
            # outer tip (far end) -- crossing the housing/platform gap and
            # the full platform depth, not just the gap alone.
            piston_rect = pygame.Rect(0, 0, PISTON_ROD_WIDTH_PX, belt_rect.top - platform_rect.top)
            piston_rect.centerx = station_x
            piston_rect.top = platform_rect.top
            pygame.draw.rect(surface, PISTON_COLOR, piston_rect)

        rotated = pygame.transform.rotate(surface, machine.placementCoordinate.degrees)
        px, py = _to_screen(machine.placementCoordinate)
        screen.blit(rotated, rotated.get_rect(center=(px, py)))
