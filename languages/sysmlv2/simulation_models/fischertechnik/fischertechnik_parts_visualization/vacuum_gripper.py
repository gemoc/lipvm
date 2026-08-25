import pygame

from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts.vacuum_gripper import (
    VacuumGripperMachine, VGR_BASE_LENGTH, VGR_BASE_WIDTH, VGR_TOWER_BASE_LENGTH, VGR_TOWER_BASE_WIDTH,
    DEFAULT_ARM_PIPE_LENGTH, MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE, MAX_ARM_ENCODER_VALUE,
)
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts_visualization.generic import MachineVisualization
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import (
    SCALE, _to_screen, TOKEN_OUTLINE_COLOR,
    PANEL_BUTTON_WIDTH, PANEL_BUTTON_HEIGHT, PANEL_BUTTON_GAP, PANEL_BUTTON_COLOR,
    PANEL_BUTTON_HOVER_COLOR, PANEL_BUTTON_TEXT_COLOR,
)
from languages.sysmlv2.simulation_models.fischertechnik.movement_computation_model import arm_encoder_to_model_size

# Farthest the arm can ever reach from center (fixed pipe + full extension)
# -- drives how big the local composite surface needs to be, since the arm
# only extends in one direction (local +x) but the surface must still be
# symmetric around the origin for the same "rotate the whole composite,
# then center-blit" trick ConveyorBeltVisualization uses to stay valid
# (pygame.transform.rotate preserves a surface's own center across
# rotation -- true regardless of what's actually drawn inside it, but only
# useful here because the origin (machine center) sits exactly at that
# surface center, which requires the surface to be symmetric around it).
VGR_MAX_REACH = DEFAULT_ARM_PIPE_LENGTH + MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE

VGR_SURFACE_WIDTH = int(2 * VGR_MAX_REACH * SCALE) + 20
VGR_SURFACE_HEIGHT = int(max(VGR_BASE_WIDTH, VGR_TOWER_BASE_WIDTH) * SCALE) + 20

VGR_BASE_COLOR = (90, 90, 100)         # the foot -- base metal plate
VGR_TOWER_COLOR = (55, 55, 65)         # the mast the arm pivots around/reaches out from
VGR_ARM_PIPE_COLOR = (120, 120, 130)   # fixed pipe, center to DEFAULT_ARM_PIPE_LENGTH -- doesn't itself extend
VGR_ARM_PIPE_WIDTH = 6                 # px
VGR_ARM_ROD_COLOR = (150, 150, 160)    # extendable segment, past the fixed pipe -- driven live by armEncoder
VGR_ARM_ROD_WIDTH = 4                  # px -- thinner than the fixed pipe, reads as the inner rod sliding out of it
VGR_GRIPPER_COLOR = (255, 195, 20)     # tip marker, at the end of the (currently zero-length) extendable segment -- brighter/more saturated than before so it pops against the base plate's cool greys even at 1px clearance from its edge
VGR_GRIPPER_OUTLINE_COLOR = TOKEN_OUTLINE_COLOR  # ring around the marker -- the marker sits mostly past the base plate's own edge, over the viewport's white BACKGROUND_COLOR/light GRID_LINE_COLOR, so it needs the same dark outline factory_visualization.py already uses to keep a light-colored shape visible against that background (a white ring would vanish there)
VGR_GRIPPER_RADIUS = 6                 # px
VGR_GRIPPER_OUTLINE_WIDTH = 2           # px


class VacuumGripperVisualization(MachineVisualization):
    """Draws a VacuumGripperMachine as seen from directly above, in three
    parts: a base (the foot -- a metal plate at ground level), a tower
    (the mast rising from the base, which the arm pivots around and
    reaches out from -- a vertical column collapses to a rectangle/circle
    in a top-down view, since it doesn't itself rotate or extend), and an
    arm reaching out from the tower.

    The arm itself has two segments: a fixed pipe from center to
    DEFAULT_ARM_PIPE_LENGTH (structural housing, never moves), and an
    extendable rod beyond that whose length tracks armEncoder live, via
    arm_encoder_to_model_size() (movement_computation_model.py). The
    machine's own placement (base/tower position, whole-composite
    rotation) is still just placementCoordinate -- rotEncoder doesn't
    drive anything here yet (no rotation behavior method exists), so the
    arm always extends straight out along local +x.
    """

    machine_type = VacuumGripperMachine
    panel_label = "Gripper"

    def panel_lines(self, machine: VacuumGripperMachine) -> list[str]:
        return [
            f"currentCommand: {machine.currentCommand}",
            f"executionStatus: {machine.executionStatus}",
            f"verticalEncoder: {machine.verticalEncoder}",
            f"armEncoder: {machine.armEncoder}",
            f"rotEncoder: {machine.rotEncoder}",
            f"vacuumActValve: {machine.vacuumActValve}",
            f"vacuumActCompressorOn: {machine.vacuumActCompressorOn}",
        ]

    def panel_buttons(self, screen: pygame.Surface, x: int, y: int, font: pygame.font.Font,
                       mouse_pos: tuple[int, int], machine: VacuumGripperMachine, on_place_token) -> list[tuple[pygame.Rect, object]]:
        """"Retract"/"Extend" call retractArm()/extendArm() directly, so the
        arm-encoder tick math (encoder_changes_per_tick/ARM_ENCODER_STEP_PER_TICK,
        movement_computation_model.py) can be checked by eye from the panel
        without a SysML scenario driving it. Both are already zero-arg bound
        methods, so no wrapping lambda is needed the way
        ConveyorBeltVisualization's buttons need one for on_place_token(m, p) --
        `on_place_token` itself goes unused here, kept only to match the
        shared MachineVisualization.panel_buttons() signature.
        """
        buttons = []
        button_x = x
        for label, action in (
            ("Retract", machine.retractArm),
            ("Extend", machine.extendArm),
        ):
            rect = pygame.Rect(button_x, y, PANEL_BUTTON_WIDTH, PANEL_BUTTON_HEIGHT)
            color = PANEL_BUTTON_HOVER_COLOR if rect.collidepoint(mouse_pos) else PANEL_BUTTON_COLOR
            pygame.draw.rect(screen, color, rect, border_radius=4)
            label_surface = font.render(label, True, PANEL_BUTTON_TEXT_COLOR)
            screen.blit(label_surface, label_surface.get_rect(center=rect.center))
            buttons.append((rect, action))
            button_x += PANEL_BUTTON_WIDTH + PANEL_BUTTON_GAP
        return buttons

    def draw(self, screen: pygame.Surface, machine: VacuumGripperMachine) -> None:
        surface = pygame.Surface((VGR_SURFACE_WIDTH, VGR_SURFACE_HEIGHT), pygame.SRCALPHA)
        center = surface.get_rect().center

        base_rect = pygame.Rect(0, 0, int(VGR_BASE_LENGTH * SCALE), int(VGR_BASE_WIDTH * SCALE))
        base_rect.center = center
        pygame.draw.rect(surface, VGR_BASE_COLOR, base_rect, border_radius=4)

        tower_rect = pygame.Rect(0, 0, int(VGR_TOWER_BASE_LENGTH * SCALE), int(VGR_TOWER_BASE_WIDTH * SCALE))
        tower_rect.center = center
        pygame.draw.rect(surface, VGR_TOWER_COLOR, tower_rect, border_radius=2)

        pipe_end = (center[0] + DEFAULT_ARM_PIPE_LENGTH * SCALE, center[1])
        pygame.draw.line(surface, VGR_ARM_PIPE_COLOR, center, pipe_end, width=VGR_ARM_PIPE_WIDTH)

        extension = arm_encoder_to_model_size(machine.armEncoder, MAX_ARM_ENCODER_VALUE, MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE)
        tip_end = (pipe_end[0] + extension * SCALE, center[1])
        pygame.draw.line(surface, VGR_ARM_ROD_COLOR, pipe_end, tip_end, width=VGR_ARM_ROD_WIDTH)
        pygame.draw.circle(surface, VGR_GRIPPER_COLOR, tip_end, VGR_GRIPPER_RADIUS)
        pygame.draw.circle(surface, VGR_GRIPPER_OUTLINE_COLOR, tip_end, VGR_GRIPPER_RADIUS, width=VGR_GRIPPER_OUTLINE_WIDTH)

        rotated = pygame.transform.rotate(surface, machine.placementCoordinate.degrees)
        px, py = _to_screen(machine.placementCoordinate)
        screen.blit(rotated, rotated.get_rect(center=(px, py)))
