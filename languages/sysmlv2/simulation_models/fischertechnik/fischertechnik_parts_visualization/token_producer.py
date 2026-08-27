import pygame

from languages.sysmlv2.simulation_models.fischertechnik.enums import TokenColorKind
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts.token_producer import (
    TokenProducerMachine, TOKEN_PROD_BASE_LENGTH, TOKEN_PROD_BASE_WIDTH,
    TOKEN_PLATFORM_LENGTH, TOKEN_PLATFORM_WIDTH, TOKEN_PLATFORM_OFFSET,
)
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts_visualization.generic import MachineVisualization
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import (
    SCALE, _to_screen, TOKEN_OUTLINE_COLOR, PANEL_TEXT_COLOR, PANEL_LINE_HEIGHT, PANEL_SUMMARY_GAP,
    PALETTE_SWATCH_SIZE, draw_color_palette,
    PANEL_BUTTON_WIDTH, PANEL_BUTTON_HEIGHT, PANEL_BUTTON_GAP, PANEL_BUTTON_COLOR,
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
    VacuumGripperVisualization already use. The drawing itself is still
    just this static picture -- TokenProducerMachine has no motion to
    animate (emitToken()/randomEmitToken()/emptyPlatform() complete in
    the single tick they're dispatched on, see token_producer.py) -- but
    its panel buttons do exercise real behavior now, not just a manual
    placement.
    """

    machine_type = TokenProducerMachine
    panel_label = "Producer"

    def panel_lines(self, machine: TokenProducerMachine) -> list[str]:
        return [
            f"currentCommand: {machine.currentCommand}",
            f"lastUsedTokenColor: {machine.lastUsedTokenColor}",
            f"platformSens: {machine.platformSens}",
        ]

    def panel_buttons(self, screen: pygame.Surface, x: int, y: int, font: pygame.font.Font,
                       mouse_pos: tuple[int, int], machine: TokenProducerMachine, selected_color: TokenColorKind,
                       on_select_color, field_values: dict) -> list[tuple[pygame.Rect, object]]:
        """A color picker (own copy, scoped to this machine's block --
        see factory_visualization.draw_color_palette()'s own docstring
        for why it lives here rather than being drawn generically once
        for the whole panel: this is the only machine kind that still
        needs one, for "Emit Token" below), then "Emit Token"/
        "Random Emit", which exercise this machine's own emitToken()/
        randomEmitToken() -- the actual perform-actions the SysML model
        calls -- so the full command -> tick() -> platformSens edge ->
        event chain can be checked by eye from the panel, same reasoning
        VacuumGripperVisualization's own (now-removed) "Pick"/"Place"/
        "Safe Pos" buttons called pick()/place()/moveToSafePosition()
        directly. "Emit Token" reads `selected_color` at click time, not
        draw time -- see MachineVisualization.panel_buttons()'s own
        docstring for why that's safe.
        """
        screen.blit(font.render("Color:", True, PANEL_TEXT_COLOR), (x, y))
        palette_y = y + PANEL_LINE_HEIGHT
        buttons = draw_color_palette(screen, x, palette_y, selected_color, on_select_color)
        button_y = palette_y + PALETTE_SWATCH_SIZE + PANEL_SUMMARY_GAP

        button_x = x
        for label, action in (
            ("Emit Token", lambda m=machine: m.emitToken(selected_color)),
            ("Random Emit", machine.randomEmitToken),
        ):
            rect = pygame.Rect(button_x, button_y, PANEL_BUTTON_WIDTH, PANEL_BUTTON_HEIGHT)
            color = PANEL_BUTTON_HOVER_COLOR if rect.collidepoint(mouse_pos) else PANEL_BUTTON_COLOR
            pygame.draw.rect(screen, color, rect, border_radius=4)
            label_surface = font.render(label, True, PANEL_BUTTON_TEXT_COLOR)
            screen.blit(label_surface, label_surface.get_rect(center=rect.center))
            buttons.append((rect, action))
            button_x += PANEL_BUTTON_WIDTH + PANEL_BUTTON_GAP
        return buttons

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
