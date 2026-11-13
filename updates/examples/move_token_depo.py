"""Example update file: move the token depot to the empty top-right of the
factory floor.

To use it during a demo, copy it into `updates/` (one level up). The update
button becomes clickable; clicking it submits the update, which is applied
once `tokenDepo` is tranquil (its `#Tranquility` constraint: no token at the
receiver), and the file is moved to `updates/applied/`. Files in this
`examples/` folder are never picked up themselves.

`tokenDepo` is declared in the model at (20.0, 35.0, 270 degrees):

    part tokenDepo : TokenDepoSystem::TokenDepo::TokenDepoMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 20.0;
            attribute :>> y = 35.0;
            attribute :>> degrees = 270.0;
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
    ChangeRuntimeAttributeValue(owner="Main::tokenDepo", attribute="placementCoordinate",
                                new_value=factory_coordinate(x=32.0, y=35.0, degrees=270.0)),
]
