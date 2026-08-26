import pygame

from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts.token_depo import (
    TokenDepoMachine, TOKEN_DEPO_BASE_LENGTH, TOKEN_DEPO_BASE_WIDTH,
    TOKEN_RECEIVER_LENGTH, TOKEN_RECEIVER_WIDTH, TOKEN_RECEIVER_OFFSET,
)
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts_visualization.generic import MachineVisualization
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import (
    SCALE, _to_screen, TOKEN_OUTLINE_COLOR,
    PANEL_BUTTON_WIDTH, PANEL_BUTTON_HEIGHT, PANEL_BUTTON_COLOR,
    PANEL_BUTTON_HOVER_COLOR, PANEL_BUTTON_TEXT_COLOR,
)

TOKEN_DEPO_BASE_COLOR = (70, 90, 110)         # cool slate housing -- this machine's where tokens end up
TOKEN_DEPO_RECEIVER_COLOR = (160, 180, 200)   # lighter surface where a stored token actually sits

# Same symmetric-surface reasoning as TokenProducerVisualization's own
# _HALF_SPAN: the receiver only extends to one side, but the surface is
# kept symmetric so the base's center lands exactly on the surface's own
# center (what pygame.transform.rotate rotates around).
_HALF_SPAN = TOKEN_DEPO_BASE_LENGTH / 2 + TOKEN_RECEIVER_LENGTH
TOKEN_DEPO_SURFACE_WIDTH = int(2 * _HALF_SPAN * SCALE) + 20
TOKEN_DEPO_SURFACE_HEIGHT = int(max(TOKEN_DEPO_BASE_WIDTH, TOKEN_RECEIVER_WIDTH) * SCALE) + 20


class TokenDepoVisualization(MachineVisualization):
    """Draws a TokenDepoMachine from directly above: a square base
    housing, and TOKEN_RECEIVER_OFFSET model units to its right (the
    machine's own local +x axis, before rotation) the platform a token is
    placed on to be stored -- the same coordinate receiver_position()
    (token_depo.py) hands back, so the drawn receiver and wherever a
    token is actually placed can never drift apart.

    Composited on one local, unrotated surface first (base centered on
    the surface's own center) then rotated as a whole and blitted
    centered on the machine's actual placementCoordinate -- same "rotate
    the composite, then center-blit" trick ConveyorBeltVisualization/
    VacuumGripperVisualization/TokenProducerVisualization already use.
    Still a static picture -- TokenDepoMachine has no tick()/behavior
    wired up yet (see its own "dummy machine" comment), so this is an
    initial, position-only view.
    """

    machine_type = TokenDepoMachine
    panel_label = "Depo"

    def panel_lines(self, machine: TokenDepoMachine) -> list[str]:
        return [
            f"currentCommand: {machine.currentCommand}",
            f"tokenCount: {machine.tokenCount}",
            f"receiverSens: {machine.receiverSens}",
        ]

    def panel_buttons(self, screen: pygame.Surface, x: int, y: int, font: pygame.font.Font,
                       mouse_pos: tuple[int, int], machine: TokenDepoMachine, on_place_token,
                       field_values: dict) -> list[tuple[pygame.Rect, object]]:
        """"Place" drops a token of the panel's currently-selected color
        (via on_place_token, same mechanism ConveyorBeltVisualization's
        own placement buttons use) at receiver_position() -- lets a token
        be delivered to this depo for manual testing before anything
        else in the model actually feeds one to it.
        """
        rect = pygame.Rect(x, y, PANEL_BUTTON_WIDTH, PANEL_BUTTON_HEIGHT)
        color = PANEL_BUTTON_HOVER_COLOR if rect.collidepoint(mouse_pos) else PANEL_BUTTON_COLOR
        pygame.draw.rect(screen, color, rect, border_radius=4)
        label_surface = font.render("Place", True, PANEL_BUTTON_TEXT_COLOR)
        screen.blit(label_surface, label_surface.get_rect(center=rect.center))
        return [(rect, lambda m=machine: on_place_token(m, m.receiver_position()))]

    def draw(self, screen: pygame.Surface, machine: TokenDepoMachine) -> None:
        surface = pygame.Surface((TOKEN_DEPO_SURFACE_WIDTH, TOKEN_DEPO_SURFACE_HEIGHT), pygame.SRCALPHA)
        center = surface.get_rect().center

        base_rect = pygame.Rect(0, 0, int(TOKEN_DEPO_BASE_LENGTH * SCALE), int(TOKEN_DEPO_BASE_WIDTH * SCALE))
        base_rect.center = center
        pygame.draw.rect(surface, TOKEN_DEPO_BASE_COLOR, base_rect, border_radius=4)

        receiver_rect = pygame.Rect(0, 0, int(TOKEN_RECEIVER_LENGTH * SCALE), int(TOKEN_RECEIVER_WIDTH * SCALE))
        receiver_rect.center = (center[0] + int(TOKEN_RECEIVER_OFFSET * SCALE), center[1])
        pygame.draw.rect(surface, TOKEN_DEPO_RECEIVER_COLOR, receiver_rect, border_radius=3)
        pygame.draw.rect(surface, TOKEN_OUTLINE_COLOR, receiver_rect, width=2, border_radius=3)

        rotated = pygame.transform.rotate(surface, machine.placementCoordinate.degrees)
        px, py = _to_screen(machine.placementCoordinate)
        screen.blit(rotated, rotated.get_rect(center=(px, py)))
