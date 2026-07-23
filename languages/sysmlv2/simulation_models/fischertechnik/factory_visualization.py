"""Pygame rendering for a Factory. The only file in this package allowed to
import pygame — Factory/ConveyorBeltMachine/Token stay free of any
rendering-library object, so they remain usable (and testable) independent
of whether a display is even available.
"""

import pygame

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import DirectionKind, TokenColorKind
from languages.sysmlv2.simulation_models.fischertechnik.parts import ConveyorBeltMachine
from languages.sysmlv2.simulation_models.fischertechnik.token import Token

VIEWPORT_SIZE = (800, 600)       # factory floor drawing area, excludes the attribute panel
PANEL_WIDTH = 300
WINDOW_SIZE = (VIEWPORT_SIZE[0] + PANEL_WIDTH, VIEWPORT_SIZE[1])
BACKGROUND_COLOR = (255, 255, 255)

PANEL_X = VIEWPORT_SIZE[0]
PANEL_BACKGROUND_COLOR = (245, 245, 245)
PANEL_DIVIDER_COLOR = (60, 60, 60)
PANEL_TEXT_COLOR = (20, 20, 20)
PANEL_LEFT_PADDING = 16
PANEL_TOP_PADDING = 16
PANEL_LINE_HEIGHT = 20
PANEL_MACHINE_GAP = 14           # extra vertical gap after each machine's block
PANEL_SUMMARY_GAP = 14           # extra vertical gap after the factory-wide summary line

PANEL_BUTTON_WIDTH = 60
PANEL_BUTTON_HEIGHT = 22
PANEL_BUTTON_GAP = 6             # horizontal gap between buttons in the same row
PANEL_BUTTON_COLOR = (210, 210, 210)
PANEL_BUTTON_HOVER_COLOR = (185, 200, 225)
PANEL_BUTTON_TEXT_COLOR = (20, 20, 20)

BELT_WIDTH = 100
BELT_HEIGHT = 35

BELT_FRAME_COLOR = (60, 60, 60)      # guide rails, visible along the belt's long edges from above
BELT_SURFACE_COLOR = (35, 35, 35)    # the belt's top surface, inset from the rails
BELT_TREAD_COLOR = (70, 70, 70)      # tread ridges, running across the belt's direction of travel
FEED_COLOR = (40, 160, 90)           # left end, in the belt's own unrotated frame: where parts enter
SWAP_COLOR = (210, 150, 30)          # right end, in the belt's own unrotated frame: where parts exit/swap
TREAD_SPACING = 10
ROLLER_BAND_WIDTH = 6

TOKEN_RADIUS = 8
TOKEN_OUTLINE_COLOR = (60, 60, 60)   # ring around every token; keeps a WHITE token visible against BACKGROUND_COLOR
TOKEN_COLORS = {
    TokenColorKind.BLUE: (30, 90, 200),
    TokenColorKind.WHITE: (255, 255, 255),
    TokenColorKind.RED: (200, 40, 40),
}


SCALE = 20                       # pixels per model unit
ORIGIN = (BELT_WIDTH // 2, VIEWPORT_SIZE[1] - BELT_HEIGHT // 2)  # bottom-left of the viewport is model (0, 0)


def to_screen(coord: FactoryCoordinate) -> tuple[int, int]:
    px = ORIGIN[0] + coord.x * SCALE
    py = ORIGIN[1] - coord.y * SCALE  # flip y: pygame's screen y grows downward
    return int(px), int(py)


def draw_conveyor_belt(screen: pygame.Surface, machine: ConveyorBeltMachine) -> None:
    """Draws the belt as seen from directly above: guide rails along its
    long edges, a flat surface with tread ridges running across the
    direction of travel, and a colored band at each end marking the feed
    end (where parts enter) and the swap end (where parts exit), in the
    belt's own unrotated left/right frame — as opposed to a side-on
    silhouette, which would show the rollers as circular ends. Still a
    static picture (matches Milestone 1 scope).

    Composited on a local, unrotated surface first because pygame's draw
    primitives have no rotation argument; the finished belt is rotated as
    one image via pygame.transform.rotate and then blitted onto the screen,
    recentered on the belt's placement coordinate.
    """
    belt_surface = pygame.Surface((BELT_WIDTH, BELT_HEIGHT), pygame.SRCALPHA)
    rect = belt_surface.get_rect()
    pygame.draw.rect(belt_surface, BELT_FRAME_COLOR, rect, border_radius=6)

    # Inset more along the height than the length: the height-inset reveals
    # the frame as rails running along the belt's long edges, while the
    # length-inset just leaves room for the roller bands at each end.
    surface_rect = rect.inflate(-8, -12)
    pygame.draw.rect(belt_surface, BELT_SURFACE_COLOR, surface_rect, border_radius=3)

    previous_clip = belt_surface.get_clip()
    belt_surface.set_clip(surface_rect)
    for x in range(surface_rect.left, surface_rect.right, TREAD_SPACING):
        pygame.draw.line(belt_surface, BELT_TREAD_COLOR, (x, surface_rect.top), (x, surface_rect.bottom), 2)
    belt_surface.set_clip(previous_clip)

    for roller_rect, color in (
        (pygame.Rect(surface_rect.left, surface_rect.top, ROLLER_BAND_WIDTH, surface_rect.height), FEED_COLOR),
        (pygame.Rect(surface_rect.right - ROLLER_BAND_WIDTH, surface_rect.top, ROLLER_BAND_WIDTH, surface_rect.height), SWAP_COLOR),
    ):
        pygame.draw.rect(belt_surface, color, roller_rect)

    rotated = pygame.transform.rotate(belt_surface, machine.placementCoordinate.degrees)
    px, py = to_screen(machine.placementCoordinate)
    screen.blit(rotated, rotated.get_rect(center=(px, py)))


def draw_token(screen: pygame.Surface, token: Token) -> None:
    """Draws a Token as a small filled circle at its current position, on
    top of whatever machine it's sitting on, colored by its TokenColorKind.
    """
    px, py = to_screen(token.position)
    pygame.draw.circle(screen, TOKEN_COLORS[token.color], (px, py), TOKEN_RADIUS)
    pygame.draw.circle(screen, TOKEN_OUTLINE_COLOR, (px, py), TOKEN_RADIUS, 1)


def draw_machine_panel(screen: pygame.Surface, machines, unowned_token_count: int, font: pygame.font.Font, label_font: pygame.font.Font) -> list[tuple[pygame.Rect, object]]:
    """Draws a side panel to the right of the viewport: a factory-wide
    summary line, then each machine's live attributes and a row of manual
    control buttons, one stacked block per machine. Machines are labeled
    by their position in `machines` ("Belt 1", "Belt 2", ...) rather than
    a real name — `ConveyorBeltMachine` doesn't carry one.
    placementCoordinate is deliberately omitted: it's already conveyed by
    the machine's drawn position in the viewport.

    Returns the list of (rect, callback) pairs for the buttons just drawn,
    so the caller's event loop can hit-test mouse clicks against them —
    computed here, in the same pass as the drawing, so the clickable area
    can never drift out of sync with what's on screen.
    """
    panel_rect = pygame.Rect(PANEL_X, 0, PANEL_WIDTH, VIEWPORT_SIZE[1])
    pygame.draw.rect(screen, PANEL_BACKGROUND_COLOR, panel_rect)
    pygame.draw.line(screen, PANEL_DIVIDER_COLOR, (PANEL_X, 0), (PANEL_X, VIEWPORT_SIZE[1]), 2)

    mouse_pos = pygame.mouse.get_pos()
    buttons = []
    x = PANEL_X + PANEL_LEFT_PADDING
    y = PANEL_TOP_PADDING

    screen.blit(font.render(f"Unowned tokens: {unowned_token_count}", True, PANEL_TEXT_COLOR), (x, y))
    y += PANEL_LINE_HEIGHT + PANEL_SUMMARY_GAP

    for index, machine in enumerate(machines, start=1):
        screen.blit(label_font.render(f"Belt {index}", True, PANEL_TEXT_COLOR), (x, y))
        y += PANEL_LINE_HEIGHT

        for line in (
            f"conveyorSensFeed: {machine.conveyorSensFeed}",
            f"conveyorSensSwap: {machine.conveyorSensSwap}",
            f"currentCommand: {machine.currentCommand}",
            f"direction: {machine.direction}",
        ):
            screen.blit(font.render(line, True, PANEL_TEXT_COLOR), (x, y))
            y += PANEL_LINE_HEIGHT

        button_x = x
        for label, callback in (
            ("Feed", lambda m=machine: m.moveToSensor(DirectionKind.BACKWARD)),
            ("Swap", lambda m=machine: m.moveToSensor(DirectionKind.FORWARD)),
            ("-1", lambda m=machine: m.moveNbSteps(1, DirectionKind.BACKWARD)),
            ("+1", lambda m=machine: m.moveNbSteps(1, DirectionKind.FORWARD)),
        ):
            rect = pygame.Rect(button_x, y, PANEL_BUTTON_WIDTH, PANEL_BUTTON_HEIGHT)
            color = PANEL_BUTTON_HOVER_COLOR if rect.collidepoint(mouse_pos) else PANEL_BUTTON_COLOR
            pygame.draw.rect(screen, color, rect, border_radius=4)
            label_surface = font.render(label, True, PANEL_BUTTON_TEXT_COLOR)
            screen.blit(label_surface, label_surface.get_rect(center=rect.center))
            buttons.append((rect, callback))
            button_x += PANEL_BUTTON_WIDTH + PANEL_BUTTON_GAP

        y += PANEL_BUTTON_HEIGHT + PANEL_MACHINE_GAP

    return buttons


def draw_factory(factory, tick_rate: int = 60) -> None:
    """Static-picture render loop: every frame, redraws every registered
    machine at its placementCoordinate. Redrawing from scratch each frame
    is required by pygame (unlike tkinter, it has no persistent canvas),
    even though nothing moves yet — Milestone 1 is static-only.
    """
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE)
    pygame.display.set_caption("Fischertechnik Factory")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 18)
    label_font = pygame.font.SysFont(None, 20, bold=True)

    running = True
    buttons: list[tuple[pygame.Rect, object]] = []
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for rect, callback in buttons:
                    if rect.collidepoint(event.pos):
                        callback()
                        break

        factory.tick()

        screen.fill(BACKGROUND_COLOR)
        for machine in factory.machines:
            draw_conveyor_belt(screen, machine)
        for token in factory.tokens:
            draw_token(screen, token)
        unowned_token_count = len(factory.tokens_on(None))
        buttons = draw_machine_panel(screen, factory.machines, unowned_token_count, font, label_font)

        pygame.display.flip()
        clock.tick(tick_rate)

    pygame.quit()
