"""Pygame rendering for a Factory. The only file in this package allowed to
import pygame — Factory/ConveyorBeltMachine/Token stay free of any
rendering-library object, so they remain usable (and testable) independent
of whether a display is even available.
"""

import pygame

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import TokenColorKind
from languages.sysmlv2.simulation_models.fischertechnik.parts import ConveyorBeltMachine
from languages.sysmlv2.simulation_models.fischertechnik.token import Token

WINDOW_SIZE = (800, 600)
BACKGROUND_COLOR = (255, 255, 255)

BELT_WIDTH = 80
BELT_HEIGHT = 30

BELT_FRAME_COLOR = (60, 60, 60)      # guide rails, visible along the belt's long edges from above
BELT_SURFACE_COLOR = (35, 35, 35)    # the belt's top surface, inset from the rails
BELT_TREAD_COLOR = (70, 70, 70)      # tread ridges, running across the belt's direction of travel
ROLLER_COLOR = (150, 150, 150)       # roller drum's top, visible as a band at each end
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
ORIGIN = (BELT_WIDTH // 2, WINDOW_SIZE[1] - BELT_HEIGHT // 2)     # bottom-left of the window is model (0, 0)


def to_screen(coord: FactoryCoordinate) -> tuple[int, int]:
    px = ORIGIN[0] + coord.x * SCALE
    py = ORIGIN[1] - coord.y * SCALE  # flip y: pygame's screen y grows downward
    return int(px), int(py)


def draw_conveyor_belt(screen: pygame.Surface, machine: ConveyorBeltMachine) -> None:
    """Draws the belt as seen from directly above: guide rails along its
    long edges, a flat surface with tread ridges running across the
    direction of travel, and a lighter band at each end where the roller
    drum's curved top is visible — as opposed to a side-on silhouette,
    which would show the rollers as circular ends. Still a static picture
    (matches Milestone 1 scope).
    """
    px, py = to_screen(machine.placementCoordinate)
    rect = pygame.Rect(px - BELT_WIDTH // 2, py - BELT_HEIGHT // 2, BELT_WIDTH, BELT_HEIGHT)
    pygame.draw.rect(screen, BELT_FRAME_COLOR, rect, border_radius=6)

    # Inset more along the height than the length: the height-inset reveals
    # the frame as rails running along the belt's long edges, while the
    # length-inset just leaves room for the roller bands at each end.
    surface_rect = rect.inflate(-8, -12)
    pygame.draw.rect(screen, BELT_SURFACE_COLOR, surface_rect, border_radius=3)

    previous_clip = screen.get_clip()
    screen.set_clip(surface_rect)
    for x in range(surface_rect.left, surface_rect.right, TREAD_SPACING):
        pygame.draw.line(screen, BELT_TREAD_COLOR, (x, surface_rect.top), (x, surface_rect.bottom), 2)
    screen.set_clip(previous_clip)

    for roller_rect in (
        pygame.Rect(surface_rect.left, surface_rect.top, ROLLER_BAND_WIDTH, surface_rect.height),
        pygame.Rect(surface_rect.right - ROLLER_BAND_WIDTH, surface_rect.top, ROLLER_BAND_WIDTH, surface_rect.height),
    ):
        pygame.draw.rect(screen, ROLLER_COLOR, roller_rect)


def draw_token(screen: pygame.Surface, token: Token) -> None:
    """Draws a Token as a small filled circle at its current position, on
    top of whatever machine it's sitting on, colored by its TokenColorKind.
    """
    px, py = to_screen(token.position)
    pygame.draw.circle(screen, TOKEN_COLORS[token.color], (px, py), TOKEN_RADIUS)
    pygame.draw.circle(screen, TOKEN_OUTLINE_COLOR, (px, py), TOKEN_RADIUS, 1)


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

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill(BACKGROUND_COLOR)
        for machine in factory.machines:
            draw_conveyor_belt(screen, machine)
        for token in factory.tokens:
            draw_token(screen, token)

        pygame.display.flip()
        clock.tick(tick_rate)

    pygame.quit()
