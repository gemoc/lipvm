import pygame

from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts.token_producer import (
    TokenProducerMachine, TOKEN_PROD_BASE_LENGTH, TOKEN_PROD_BASE_WIDTH,
    TOKEN_PLATFORM_LENGTH, TOKEN_PLATFORM_WIDTH, TOKEN_PLATFORM_OFFSET,
)
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts_visualization.generic import MachineVisualization
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import (
    SCALE, _to_screen, TOKEN_OUTLINE_COLOR,
    PANEL_BUTTON_WIDTH, PANEL_BUTTON_HEIGHT, PANEL_BUTTON_COLOR,
    PANEL_BUTTON_HOVER_COLOR, PANEL_BUTTON_TEXT_COLOR,
)

TOKEN_PROD_BASE_COLOR = (150, 100, 60)      # warm brown housing -- this machine's the source of tokens
TOKEN_PROD_PLATFORM_COLOR = (220, 190, 140) # lighter surface where a produced token actually sits

# Surface sized symmetrically around the base's own center (surface center
# stands in for placementCoordinate, same as ConveyorBeltVisualization's
# belt_surface) -- the platform only extends to one side, so the surface
# only needs to reach TOKEN_PLATFORM_OFFSET + half the platform's own
# length past center on the +x side, but is kept symmetric so the base's
# center lands exactly on the surface's own center (what
# pygame.transform.rotate rotates around).
_HALF_SPAN = TOKEN_PROD_BASE_LENGTH / 2 + TOKEN_PLATFORM_LENGTH
TOKEN_PROD_SURFACE_WIDTH = int(2 * _HALF_SPAN * SCALE) + 20
TOKEN_PROD_SURFACE_HEIGHT = int(max(TOKEN_PROD_BASE_WIDTH, TOKEN_PLATFORM_WIDTH) * SCALE) + 20


class TokenProducerVisualization(MachineVisualization):
    """Draws a TokenProducerMachine from directly above: a square base
    housing, and TOKEN_PLATFORM_OFFSET model units to its right (the
    machine's own local +x axis, before rotation) the platform a produced
    token is placed on -- the same coordinate platform_position()
    (token_producer.py) hands back, so the drawn platform and wherever a
    token actually appears can never drift apart.

    Composited on one local, unrotated surface first (base centered on
    the surface's own center) then rotated as a whole and blitted
    centered on the machine's actual placementCoordinate -- same "rotate
    the composite, then center-blit" trick ConveyorBeltVisualization/
    VacuumGripperVisualization already use. Still a static picture --
    TokenProducerMachine has no tick()/behavior wired up yet (see its own
    "dummy machine" comment), so this is an initial, position-only view.
    """

    machine_type = TokenProducerMachine
    panel_label = "Producer"

    def panel_lines(self, machine: TokenProducerMachine) -> list[str]:
        return [
            f"currentCommand: {machine.currentCommand}",
            f"lastUsedTokenColor: {machine.lastUsedTokenColor}",
        ]

    def panel_buttons(self, screen: pygame.Surface, x: int, y: int, font: pygame.font.Font,
                       mouse_pos: tuple[int, int], machine: TokenProducerMachine, on_place_token,
                       field_values: dict) -> list[tuple[pygame.Rect, object]]:
        """"Place" spawns a token of the panel's currently-selected color
        (via on_place_token, same mechanism ConveyorBeltVisualization's
        own placement buttons use) at platform_position() -- the one
        thing this dummy machine can't yet do for itself, since nothing
        drives its state machine's randomEmitToken behavior into an
        actual token yet.
        """
        rect = pygame.Rect(x, y, PANEL_BUTTON_WIDTH, PANEL_BUTTON_HEIGHT)
        color = PANEL_BUTTON_HOVER_COLOR if rect.collidepoint(mouse_pos) else PANEL_BUTTON_COLOR
        pygame.draw.rect(screen, color, rect, border_radius=4)
        label_surface = font.render("Place", True, PANEL_BUTTON_TEXT_COLOR)
        screen.blit(label_surface, label_surface.get_rect(center=rect.center))
        return [(rect, lambda m=machine: on_place_token(m, m.platform_position()))]

    def draw(self, screen: pygame.Surface, machine: TokenProducerMachine) -> None:
        surface = pygame.Surface((TOKEN_PROD_SURFACE_WIDTH, TOKEN_PROD_SURFACE_HEIGHT), pygame.SRCALPHA)
        center = surface.get_rect().center

        base_rect = pygame.Rect(0, 0, int(TOKEN_PROD_BASE_LENGTH * SCALE), int(TOKEN_PROD_BASE_WIDTH * SCALE))
        base_rect.center = center
        pygame.draw.rect(surface, TOKEN_PROD_BASE_COLOR, base_rect, border_radius=4)

        platform_rect = pygame.Rect(0, 0, int(TOKEN_PLATFORM_LENGTH * SCALE), int(TOKEN_PLATFORM_WIDTH * SCALE))
        platform_rect.center = (center[0] + int(TOKEN_PLATFORM_OFFSET * SCALE), center[1])
        pygame.draw.rect(surface, TOKEN_PROD_PLATFORM_COLOR, platform_rect, border_radius=3)
        pygame.draw.rect(surface, TOKEN_OUTLINE_COLOR, platform_rect, width=2, border_radius=3)

        rotated = pygame.transform.rotate(surface, machine.placementCoordinate.degrees)
        px, py = _to_screen(machine.placementCoordinate)
        screen.blit(rotated, rotated.get_rect(center=(px, py)))
