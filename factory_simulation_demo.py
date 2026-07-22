"""Standalone demo for `factory_visualization.py`, deliberately decoupled
from the SysML interpreter: builds a Factory and a couple of
ConveyorBeltMachine instances by hand, with hardcoded placementCoordinates,
so the rendering pipeline can be developed and visually verified before
it's wired to real model-instantiated parts (see MILESTONE1.md, steps 3-5).
"""

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import TokenColorKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import draw_factory, BELT_WIDTH, SCALE
from languages.sysmlv2.simulation_models.fischertechnik.parts import ConveyorBeltMachine
from languages.sysmlv2.simulation_models.fischertechnik.token import Token

# Offset from a belt's own placementCoordinate to its feed/swap end, in model
# units. Only valid along a belt's own unrotated x-axis, which is why the
# feed/swap cases below are only used on belt1/belt3 (both at 0 degrees) —
# the rotated belt2 takes the "middle" case instead, which needs no offset.
BELT_HALF_LENGTH_UNITS = BELT_WIDTH // 2 // SCALE


def build_demo_factory() -> Factory:
    factory = Factory()

    belt1 = ConveyorBeltMachine(factory)
    belt1.placementCoordinate = FactoryCoordinate(0, 0, 0)
    factory.register_machine(belt1)

    belt2 = ConveyorBeltMachine(factory)
    belt2.placementCoordinate = FactoryCoordinate(6, 2, 90)
    factory.register_machine(belt2)

    belt3 = ConveyorBeltMachine(factory)
    belt3.placementCoordinate = FactoryCoordinate(12, 5, 0)
    factory.register_machine(belt3)

    # belt1: token sits at the swap (right) end.
    token1 = Token("T1", FactoryCoordinate(0 + BELT_HALF_LENGTH_UNITS, 0, 0), TokenColorKind.BLUE)
    factory.spawn_token(token1, belt1)

    # belt2: token sits in the middle (belt2 is rotated, so this is the only
    # case that doesn't need rotating the offset along with it).
    token2 = Token("T2", FactoryCoordinate(6, 2, 0), TokenColorKind.WHITE)
    factory.spawn_token(token2, belt2)

    # belt3: token sits at the feed (left) end.
    token3 = Token("T3", FactoryCoordinate(12 - BELT_HALF_LENGTH_UNITS, 5, 0), TokenColorKind.RED)
    factory.spawn_token(token3, belt3)

    return factory


def main() -> None:
    factory = build_demo_factory()
    draw_factory(factory)


if __name__ == "__main__":
    main()
