import pygame

from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts.conveyor_belt import ConveyorBeltMachine, FEED_TO_SWAP_LENGTH
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts_visualization.generic import MachineVisualization
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import (
    BELT_WIDTH, BELT_HEIGHT, BELT_FRAME_COLOR, BELT_SURFACE_COLOR, BELT_TREAD_COLOR,
    FEED_COLOR, SWAP_COLOR, TREAD_SPACING, ROLLER_BAND_WIDTH, SCALE, _to_screen,
)


class ConveyorBeltVisualization(MachineVisualization):
    """Draws a ConveyorBeltMachine as seen from directly above: guide
    rails along its long edges, a flat surface with tread ridges running
    across the direction of travel, and a colored band marking the feed
    sensor (where parts enter) and the swap sensor (where parts exit) at
    their actual model-coordinate positions -- FEED_TO_SWAP_LENGTH / 2
    from center, not the edges of the drawn belt, since BELT_WIDTH is
    drawn wider than that to also cover the overshoot zone (see
    CB_LENGTH) -- in the belt's own unrotated left/right frame, as
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

    No panel_buttons() override -- falls back to
    MachineVisualization.panel_buttons()'s own "no buttons" default.
    There used to be "Pre"/"Feed"/"Swap"/"Post" buttons dropping a
    manual token at each sensor boundary; removed once they stopped
    being useful enough to keep around -- this machine's own movement
    (moveToSensor()/moveOut()/moveNbSteps()) is already driven entirely
    by the SysML model's own `do`/`accept when` behavior
    (vgr-cb-true-simulation.xmi's ConveyorBeltSimpleMission), proven
    working end-to-end, so a manual panel control duplicating that isn't
    needed to exercise this machine kind anymore.
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
