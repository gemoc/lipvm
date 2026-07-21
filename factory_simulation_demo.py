"""Standalone demo for `factory_visualization.py`, deliberately decoupled
from the SysML interpreter: builds a Factory and a couple of
ConveyorBeltMachine instances by hand, with hardcoded placementCoordinates,
so the rendering pipeline can be developed and visually verified before
it's wired to real model-instantiated parts (see MILESTONE1.md, steps 3-5).
"""

from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import draw_factory
from languages.sysmlv2.simulation_models.fischertechnik.parts import ConveyorBeltMachine


def build_demo_factory() -> Factory:
    factory = Factory()

    belt1 = ConveyorBeltMachine(factory)
    belt1.placementCoordinate = FactoryCoordinate(0, 0)
    factory.register_machine(belt1)

    belt2 = ConveyorBeltMachine(factory)
    belt2.placementCoordinate = FactoryCoordinate(6, 2)
    factory.register_machine(belt2)

    return factory


def main() -> None:
    factory = build_demo_factory()
    draw_factory(factory)


if __name__ == "__main__":
    main()
