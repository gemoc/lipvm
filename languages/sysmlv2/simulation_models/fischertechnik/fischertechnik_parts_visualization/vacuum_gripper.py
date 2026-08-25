import pygame

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import Position3D
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts.vacuum_gripper import (
    VacuumGripperMachine, VGR_BASE_LENGTH, VGR_BASE_WIDTH, VGR_TOWER_BASE_LENGTH, VGR_TOWER_BASE_WIDTH,
    DEFAULT_ARM_PIPE_LENGTH, MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE, MAX_ARM_ENCODER_VALUE, MAX_ROT_ENCODER_VALUE,
)
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts_visualization.generic import MachineVisualization
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import (
    SCALE, _to_screen, TOKEN_OUTLINE_COLOR, PANEL_TEXT_COLOR,
    PANEL_BUTTON_WIDTH, PANEL_BUTTON_HEIGHT, PANEL_BUTTON_GAP, PANEL_BUTTON_COLOR,
    PANEL_BUTTON_HOVER_COLOR, PANEL_BUTTON_TEXT_COLOR,
    INPUT_FIELD_WIDTH, INPUT_FIELD_HEIGHT, INPUT_FIELD_LABEL_WIDTH, INPUT_FIELD_GROUP_GAP, INPUT_FIELD_ROW_GAP,
    INPUT_FIELD_BACKGROUND_COLOR, INPUT_FIELD_BORDER_COLOR, INPUT_FIELD_FOCUSED_BORDER_COLOR, INPUT_FIELD_TEXT_COLOR,
)
from languages.sysmlv2.simulation_models.fischertechnik.movement_computation_model import arm_encoder_to_model_size, rot_encoder_to_degrees


def _parse_field(field_values: dict, key: str) -> float:
    """Parses a text input field's current string into a float,
    defaulting to 0.0 for an empty/missing field or an in-progress,
    not-yet-complete entry (a bare "-" or "."). Character filtering at
    typing time (factory_visualization.py's _is_valid_numeric_input_char)
    already keeps a field's content float()-parseable once it's a
    complete number -- this just covers the moment before it is, so a
    button click mid-typing degrades to "treat as 0" rather than
    crashing the whole action.
    """
    text = field_values.get(key, "").strip()
    if not text or text in ("-", "."):
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0

# Farthest the arm can ever reach from center (fixed pipe + full extension)
# -- drives how big the local composite surface needs to be. Square, not
# just wide: the arm's *drawing* is always along local +x before rotation,
# but rotEncoder (VacuumGripperMachine) can point the whole arm in any
# direction once rotated onto the composite -- a surface only tall enough
# for the base/tower (as it used to be, back when the arm never rotated
# independently) would clip the tip off-canvas the moment the arm swings
# toward vertical (e.g. 90/270 degrees), even though the horizontal resting
# angles look fine. Same "rotate the whole composite, then center-blit"
# trick ConveyorBeltVisualization uses to stay valid (pygame.transform.rotate
# preserves a surface's own center across rotation -- true regardless of
# what's drawn inside it, but only useful here because the origin (machine
# center) sits exactly at that surface center, which requires the surface
# to be symmetric around it).
VGR_MAX_REACH = DEFAULT_ARM_PIPE_LENGTH + MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE

VGR_SURFACE_WIDTH = int(2 * VGR_MAX_REACH * SCALE) + 20
VGR_SURFACE_HEIGHT = VGR_SURFACE_WIDTH

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
    arm_encoder_to_model_size() (movement_computation_model.py). The whole
    arm also swivels around the tower live, tracking rotEncoder via
    rot_encoder_to_degrees() -- a separate rotation stage from the
    machine's own placement (base/tower position, whole-composite
    rotation via placementCoordinate.degrees), since the arm's swivel is
    independent of where the machine itself sits/faces in the factory.
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

    def panel_input_fields(self, screen: pygame.Surface, x: int, y: int, font: pygame.font.Font,
                            machine: VacuumGripperMachine, field_values: dict, focused_field
                            ) -> list[tuple[str, pygame.Rect]]:
        """Two rows: "Target" (horizontal/rot -- used by goToPosition() and
        doubles as move()'s endPosition) and "Move start" (horizontal/rot
        -- move()'s startPosition only). One shared "target" pair rather
        than 6 fully independent fields, since goToPosition and move's end
        are the same underlying concept (where the arm should end up).
        """
        fields = []
        row_y = y
        for row_label, keys in (
            ("Target", ("target_horizontal", "target_rot")),
            ("Move start", ("move_start_horizontal", "move_start_rot")),
        ):
            field_x = x
            row_label_surface = font.render(f"{row_label}:", True, PANEL_TEXT_COLOR)
            screen.blit(row_label_surface, (field_x, row_y + (INPUT_FIELD_HEIGHT - row_label_surface.get_height()) // 2))
            field_x += INPUT_FIELD_LABEL_WIDTH

            for axis_label, key in zip(("H", "Rot"), keys):
                axis_surface = font.render(f"{axis_label}:", True, PANEL_TEXT_COLOR)
                screen.blit(axis_surface, (field_x, row_y + (INPUT_FIELD_HEIGHT - axis_surface.get_height()) // 2))
                field_x += axis_surface.get_width() + 4

                rect = pygame.Rect(field_x, row_y, INPUT_FIELD_WIDTH, INPUT_FIELD_HEIGHT)
                border_color = INPUT_FIELD_FOCUSED_BORDER_COLOR if key == focused_field else INPUT_FIELD_BORDER_COLOR
                pygame.draw.rect(screen, INPUT_FIELD_BACKGROUND_COLOR, rect)
                pygame.draw.rect(screen, border_color, rect, width=2)
                text_surface = font.render(field_values.get(key, ""), True, INPUT_FIELD_TEXT_COLOR)
                screen.blit(text_surface, (rect.x + 4, rect.y + (rect.height - text_surface.get_height()) // 2))
                fields.append((key, rect))

                field_x += INPUT_FIELD_WIDTH + INPUT_FIELD_GROUP_GAP

            row_y += INPUT_FIELD_HEIGHT + INPUT_FIELD_ROW_GAP

        return fields

    def panel_buttons(self, screen: pygame.Surface, x: int, y: int, font: pygame.font.Font,
                       mouse_pos: tuple[int, int], machine: VacuumGripperMachine, on_place_token,
                       field_values: dict) -> list[tuple[pygame.Rect, object]]:
        """"Go to Pos"/"Move"/"Safe Pos"/"Grip"/"Release" exercise
        goToPosition()/move()/moveToSafePosition()/grip()/release()
        directly, so the encoder tick math and vacuum-flag flips can be
        checked by eye from the panel without a SysML scenario driving it.
        goToPosition/move read their target(s) from `field_values` at
        click time, not draw time -- panel_buttons() is rebuilt fresh
        every frame, so each callback closure always captures whatever's
        currently typed the moment it's actually clicked (same reasoning
        ConveyorBeltVisualization's token-placement buttons already rely
        on for the panel's selected color). `on_place_token` goes unused
        here, kept only to match the shared
        MachineVisualization.panel_buttons() signature.
        """
        def handle_go_to_position():
            machine.goToPosition(Position3D(
                vertical=0.0,
                horizontal=_parse_field(field_values, "target_horizontal"),
                rot=_parse_field(field_values, "target_rot"),
            ))

        def handle_move():
            machine.move(
                Position3D(vertical=0.0,
                           horizontal=_parse_field(field_values, "move_start_horizontal"),
                           rot=_parse_field(field_values, "move_start_rot")),
                Position3D(vertical=0.0,
                           horizontal=_parse_field(field_values, "target_horizontal"),
                           rot=_parse_field(field_values, "target_rot")),
            )

        buttons = []
        button_x = x
        for label, action in (
            ("Go to Pos", handle_go_to_position),
            ("Move", handle_move),
            ("Safe Pos", machine.moveToSafePosition),
            ("Grip", machine.grip),
            ("Release", machine.release),
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

        # Arm (pipe + rod + gripper tip) drawn on its own same-size surface
        # along local +x, then rotated around its own center by the live
        # rotEncoder angle before being blitted onto the base/tower
        # composite -- kept as a separate rotation stage from the
        # whole-machine one below (placementCoordinate.degrees, this
        # VacuumGripperMachine's fixed orientation in the factory), since
        # the arm swivels around the tower independently of that. Using
        # the same VGR_SURFACE_WIDTH/HEIGHT for arm_surface as the main
        # composite is what makes centering the rotated result trivial:
        # both surfaces share the same center point, so blitting at
        # `center` lines them up regardless of the rotation angle (same
        # "rotate the whole composite, then center-blit" trick used below,
        # applied one level deeper).
        arm_surface = pygame.Surface((VGR_SURFACE_WIDTH, VGR_SURFACE_HEIGHT), pygame.SRCALPHA)
        arm_center = arm_surface.get_rect().center

        pipe_end = (arm_center[0] + DEFAULT_ARM_PIPE_LENGTH * SCALE, arm_center[1])
        pygame.draw.line(arm_surface, VGR_ARM_PIPE_COLOR, arm_center, pipe_end, width=VGR_ARM_PIPE_WIDTH)

        extension = arm_encoder_to_model_size(machine.armEncoder, MAX_ARM_ENCODER_VALUE, MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE)
        tip_end = (pipe_end[0] + extension * SCALE, arm_center[1])
        pygame.draw.line(arm_surface, VGR_ARM_ROD_COLOR, pipe_end, tip_end, width=VGR_ARM_ROD_WIDTH)
        pygame.draw.circle(arm_surface, VGR_GRIPPER_COLOR, tip_end, VGR_GRIPPER_RADIUS)
        pygame.draw.circle(arm_surface, VGR_GRIPPER_OUTLINE_COLOR, tip_end, VGR_GRIPPER_RADIUS, width=VGR_GRIPPER_OUTLINE_WIDTH)

        arm_rotation_degrees = rot_encoder_to_degrees(machine.rotEncoder, MAX_ROT_ENCODER_VALUE)
        rotated_arm = pygame.transform.rotate(arm_surface, arm_rotation_degrees)
        surface.blit(rotated_arm, rotated_arm.get_rect(center=center))

        rotated = pygame.transform.rotate(surface, machine.placementCoordinate.degrees)
        px, py = _to_screen(machine.placementCoordinate)
        screen.blit(rotated, rotated.get_rect(center=(px, py)))
