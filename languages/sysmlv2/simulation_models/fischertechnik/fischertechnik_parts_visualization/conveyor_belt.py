import pygame

from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts.conveyor_belt import ConveyorBeltMachine, FEED_TO_SWAP_LENGTH
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts_visualization.generic import MachineVisualization
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import (
    BELT_WIDTH, BELT_HEIGHT, BELT_FRAME_COLOR, BELT_SURFACE_COLOR, BELT_TREAD_COLOR,
    FEED_COLOR, SWAP_COLOR, TREAD_SPACING, ROLLER_BAND_WIDTH, SCALE, _to_screen,
    PANEL_BUTTON_WIDTH, PANEL_BUTTON_HEIGHT, PANEL_BUTTON_GAP, PANEL_BUTTON_COLOR,
    PANEL_BUTTON_HOVER_COLOR, PANEL_BUTTON_TEXT_COLOR,
)


class ConveyorBeltVisualization(MachineVisualization):
    """Draws a ConveyorBeltMachine as seen from directly above: guide
    rails along its long edges, a flat surface with tread ridges running
    across the direction of travel, and a colored band marking the feed
    sensor (where parts enter) and the swap sensor (where parts exit) at
    their actual model-coordinate positions -- FEED_TO_SWAP_LENGTH / 2
    from center, not the edges of the drawn belt, since BELT_WIDTH is
    drawn wider than that to also cover the overshoot zone (see
    FULL_LENGTH) -- in the belt's own unrotated left/right frame, as
    opposed to a side-on silhouette, which would show the rollers as
    circular ends. Still a static picture (matches Milestone 1 scope).

    Composited on a local, unrotated surface first because pygame's draw
    primitives have no rotation argument; the finished belt is rotated as
    one image via pygame.transform.rotate and then blitted onto the
    screen, recentered on the belt's placement coordinate.

    Pulls its shared viewport constants/helper (`BELT_WIDTH`/`SCALE`/
    `_to_screen`/etc.) from `factory_visualization.py` rather than
    duplicating them -- safe against circular imports since
    `factory_visualization.py` never imports this module directly, only
    discovers it at runtime via `scan_for_subclasses(MachineVisualization)`
    (`registry.py`), by which point `factory_visualization.py` is already
    fully loaded.
    """

    machine_type = ConveyorBeltMachine
    panel_label = "Belt"

    def panel_lines(self, machine: ConveyorBeltMachine) -> list[str]:
        return [
            f"conveyorSensFeed: {machine.conveyorSensFeed}",
            f"conveyorSensSwap: {machine.conveyorSensSwap}",
            f"currentCommand: {machine.currentCommand}",
            f"direction: {machine.direction}",
        ]

    def panel_buttons(self, screen: pygame.Surface, x: int, y: int, font: pygame.font.Font,
                       mouse_pos: tuple[int, int], machine: ConveyorBeltMachine, on_place_token) -> list[tuple[pygame.Rect, object]]:
        """"Pre-Feed"/"Feed"/"Swap"/"Post-Swap" spawn a token of the
        panel's currently-selected color, owned by `machine`, at
        `machine.pre_feed_position()`/`feed_position()`/`swap_position()`/
        `post_swap_position()` respectively -- the belt's own FULL_LENGTH
        boundary on each side plus its two sensors, not an arbitrary click
        position (see conveyor_belt.py: FULL_LENGTH is already "one step"
        beyond the sensors in the model's own movement logic, reused here
        rather than inventing a new distance). The one manual control
        left now that guard evaluation/action dispatch are both wired up
        (movement itself comes only from the model's own `do`/
        `accept when` behavior) -- placing a token is the one thing the
        model can't do for itself, since nothing manufactures tokens.
        """
        buttons = []
        button_x = x
        for label, position in (
            ("Pre", machine.pre_feed_position()),
            ("Feed", machine.feed_position()),
            ("Swap", machine.swap_position()),
            ("Post", machine.post_swap_position()),
        ):
            rect = pygame.Rect(button_x, y, PANEL_BUTTON_WIDTH, PANEL_BUTTON_HEIGHT)
            color = PANEL_BUTTON_HOVER_COLOR if rect.collidepoint(mouse_pos) else PANEL_BUTTON_COLOR
            pygame.draw.rect(screen, color, rect, border_radius=4)
            label_surface = font.render(label, True, PANEL_BUTTON_TEXT_COLOR)
            screen.blit(label_surface, label_surface.get_rect(center=rect.center))
            buttons.append((rect, lambda m=machine, p=position: on_place_token(m, p)))
            button_x += PANEL_BUTTON_WIDTH + PANEL_BUTTON_GAP
        return buttons

    def draw(self, screen: pygame.Surface, machine: ConveyorBeltMachine) -> None:
        belt_surface = pygame.Surface((BELT_WIDTH, BELT_HEIGHT), pygame.SRCALPHA)
        rect = belt_surface.get_rect()
        pygame.draw.rect(belt_surface, BELT_FRAME_COLOR, rect, border_radius=6)

        # Inset more along the height than the length: the height-inset reveals
        # the frame as rails running along the belt's long edges, while the
        # length-inset just leaves a little room around the sensor bands.
        surface_rect = rect.inflate(-8, -12)
        pygame.draw.rect(belt_surface, BELT_SURFACE_COLOR, surface_rect, border_radius=3)

        previous_clip = belt_surface.get_clip()
        belt_surface.set_clip(surface_rect)
        for x in range(surface_rect.left, surface_rect.right, TREAD_SPACING):
            pygame.draw.line(belt_surface, BELT_TREAD_COLOR, (x, surface_rect.top), (x, surface_rect.bottom), 2)
        belt_surface.set_clip(previous_clip)

        sensor_offset_px = int(FEED_TO_SWAP_LENGTH / 2 * SCALE)
        for sensor_x, color in (
            (rect.centerx - sensor_offset_px, FEED_COLOR),
            (rect.centerx + sensor_offset_px, SWAP_COLOR),
        ):
            roller_rect = pygame.Rect(0, surface_rect.top, ROLLER_BAND_WIDTH, surface_rect.height)
            roller_rect.centerx = sensor_x
            pygame.draw.rect(belt_surface, color, roller_rect)

        rotated = pygame.transform.rotate(belt_surface, machine.placementCoordinate.degrees)
        px, py = _to_screen(machine.placementCoordinate)
        screen.blit(rotated, rotated.get_rect(center=(px, py)))
