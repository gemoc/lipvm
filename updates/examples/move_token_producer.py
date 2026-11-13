"""Example update file: move the token producer up to the empty upper-left of
the factory floor.

To use it during a demo, copy it into `updates/` (one level up). The update
button becomes clickable; clicking it submits the update, which is applied
once `tokenProd` is tranquil (its `#Tranquility` constraint: no token on its
platform, `platformSens == false`), and the file is moved to
`updates/applied/`. Files in this `examples/` folder are never picked up
themselves.

`tokenProd` is declared in the model at (5.0, 20.0, 0 degrees):

    part tokenProd: TokenProducerSystem::TokenProducer::TokenProducerMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 5.0;
            attribute :>> y = 20.0;
            attribute :>> degrees = 0.0;
        }
    }
"""
from languages.sysmlv2 import runtime as rt
from languages.sysmlv2.runtime_utility import ScalarType, TypeKind
from languages.sysmlv2.updates import ChangeRuntimeAttributeValue


def factory_coordinate(x: float, y: float, degrees: float) -> rt.CompositeCustomValue:
    """A `placementCoordinate` value (a `Common::FactoryCoordinate`), shaped
    like the ones built from `attribute :>> placementCoordinate { ... }`."""
    return rt.CompositeCustomValue(
        type=rt.TypeRef(kind=TypeKind.CUSTOM, reference_type=rt.Reference(
            qualified_name="Common::FactoryCoordinate", reference_type="CustomAttributeDefinition")),
        elements=[rt.Argument(name=name, value=rt.LiteralValue(el=str(value), scalar_type=ScalarType.REAL))
                  for name, value in (("x", x), ("y", y), ("degrees", degrees))])


# Submitted together as one AtomicUpdate: applied at the same checkpoint,
# once every part they change is tranquil, all or nothing.
UPDATES = [
    ChangeRuntimeAttributeValue(owner="Main::tokenProd", attribute="placementCoordinate",
                                new_value=factory_coordinate(x=5.0, y=30.0, degrees=0.0)),
]
