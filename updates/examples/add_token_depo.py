"""Example update file: add a second token depot, `tokenDepo2`, in the empty
bottom-right of the factory floor.

To use it during a demo, copy it into `updates/` (one level up). The update
button becomes clickable; clicking it submits the update, and the file is moved
to `updates/applied/`. Adding a part is always tranquil (a new part has no
running state and nothing bound to it), so it is applied at the next
checkpoint, whatever the other machines are doing.

The new depot is idle: no state machine is bound to it, so nothing delivers
tokens to it. It still takes part in tranquility through its part def, so a
later update moving it waits until no token is at its receiver.

Equivalent to declaring, next to `tokenDepo` in the model:

    part tokenDepo2 : TokenDepoSystem::TokenDepo::TokenDepoMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 32.0;
            attribute :>> y = 10.0;
            attribute :>> degrees = 0.0;
        }
    }
"""
from languages.sysmlv2 import runtime as rt
from languages.sysmlv2.runtime_utility import ScalarType, TypeKind
from languages.sysmlv2.updates import AddPartInstantiation


def factory_coordinate(x: float, y: float, degrees: float) -> rt.CompositeCustomValue:
    """A `placementCoordinate` value (a `Common::FactoryCoordinate`), shaped
    like the ones built from `attribute :>> placementCoordinate { ... }`."""
    return rt.CompositeCustomValue(
        type=rt.TypeRef(kind=TypeKind.CUSTOM, reference_type=rt.Reference(
            qualified_name="Common::FactoryCoordinate", reference_type="CustomAttributeDefinition")),
        elements=[rt.Argument(name=name, value=rt.LiteralValue(el=str(value), scalar_type=ScalarType.REAL))
                  for name, value in (("x", x), ("y", y), ("degrees", degrees))])


# Submitted together as one AtomicUpdate: applied at the same checkpoint,
# all or nothing.
UPDATES = [
    AddPartInstantiation(qualified_name="Main::tokenDepo2",
                         part_def="TokenDepoSystem::TokenDepo::TokenDepoMachine",
                         attribute_values={"placementCoordinate": factory_coordinate(x=32.0, y=10.0, degrees=0.0)}),
]
