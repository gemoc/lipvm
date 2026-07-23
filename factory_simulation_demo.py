"""Standalone demo for `factory_visualization.py`, deliberately decoupled
from the SysML interpreter: builds a Factory and a couple of
ConveyorBeltMachine instances by hand, with hardcoded placementCoordinates,
so the rendering pipeline can be developed and visually verified before
it's wired to real model-instantiated parts (see MILESTONE1.md, steps 3-5).
"""

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import TokenColorKind
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import draw_factory
from languages.sysmlv2.simulation_models.fischertechnik.parts import ConveyorBeltMachine
from languages.sysmlv2.simulation_models.fischertechnik.token import Token


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

    # belt1: token sits at the swap end, read from the belt itself so it's
    # guaranteed to match what conveyorSensSwap checks.
    token1 = Token("T1", belt1.swap_position(), TokenColorKind.BLUE)
    factory.spawn_token(token1, belt1)

    # belt2: token sits in the middle (belt2 is rotated, so this is the only
    # case that doesn't exercise the feed/swap rotation math).
    token2 = Token("T2", FactoryCoordinate(6, 2, 0), TokenColorKind.WHITE)
    factory.spawn_token(token2, belt2)

    # belt3: token sits at the feed end.
    token3 = Token("T3", belt3.feed_position(), TokenColorKind.RED)
    factory.spawn_token(token3, belt3)

    return factory


def main() -> None:
    factory = build_demo_factory()
    draw_factory(factory)


if __name__ == "__main__":
    main()
