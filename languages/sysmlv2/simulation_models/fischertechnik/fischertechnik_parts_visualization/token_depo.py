import pygame

from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts.token_depo import (
    TokenDepoMachine, TOKEN_DEPO_BASE_LENGTH, TOKEN_DEPO_BASE_WIDTH,
    TOKEN_RECEIVER_LENGTH, TOKEN_RECEIVER_WIDTH, TOKEN_RECEIVER_OFFSET,
)
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts_visualization.generic import MachineVisualization
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import (
    SCALE, _to_screen, TOKEN_OUTLINE_COLOR,
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
    The drawing itself is still just this static picture --
    TokenDepoMachine has no motion to animate (storeToken()/
    emptyReceiver() complete in the single tick they're dispatched on,
    see token_depo.py).

    No panel_buttons() override -- falls back to
    MachineVisualization.panel_buttons()'s own "no buttons" default.
    There used to be a manual "Place" button here (dropping a token
    directly via Factory.spawn_token(), bypassing this machine
    entirely), since nothing else in the simulation could deliver a
    token to the receiver yet. Removed once that stopped being useful
    enough to keep around -- until TokenProducerMachine/VGR are wired to
    actually hand a token off to this depo, there is currently no way to
    get a token onto the receiver from the UI at all.
    """

    machine_type = TokenDepoMachine
    panel_label = "Depo"

    def panel_lines(self, machine: TokenDepoMachine) -> list[str]:
        return [
            f"currentCommand: {machine.currentCommand}",
            f"tokenCount: {machine.tokenCount}",
            f"receiverSens: {machine.receiverSens}",
        ]

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
