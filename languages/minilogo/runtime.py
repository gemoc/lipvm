from pyecore.ecore import *

from core.language import AbstractSyntaxElement, RuntimeStateElement

PenStatus = EEnum("PenStatus")
PenStatus.eLiterals.append(EEnumLiteral("up"))
PenStatus.eLiterals.append(EEnumLiteral("down"))

class ColorCode(AbstractSyntaxElement, metaclass=MetaEClass):
    r = EAttribute(eType=EInt, default_value=0)
    g = EAttribute(eType=EInt, default_value=0)
    b = EAttribute(eType=EInt, default_value=0)

# Runtime State Classes (MiniLogo Specifics)
class Coordinates(EObject, metaclass=MetaEClass):
    x = EAttribute(eType=EInt)
    y = EAttribute(eType=EInt)

class Line(EObject, metaclass=MetaEClass):
    color = EReference(eType=ColorCode, lower=1, upper=1, containment=False)
    start = EReference(eType=Coordinates, lower=1, upper=1, containment=False)
    end = EReference(eType=Coordinates, lower=1, upper=1, containment=False)

class Drawing(RuntimeStateElement, metaclass=MetaEClass):
    lines = EReference(eType=Line, lower=0, upper=-1, containment=True)

class PenState(RuntimeStateElement, metaclass=MetaEClass):
    status = EAttribute(eType=PenStatus)
    position = EReference(eType=Coordinates, lower=1, upper=1, containment=False)
    color = EReference(eType=ColorCode, lower=1, upper=1, containment=False)

class VariableBinding(EObject, metaclass=MetaEClass):
    name = EAttribute(eType=EString)
    value = EAttribute(eType=EInt)

class Scope(RuntimeStateElement, metaclass=MetaEClass):
    bindings = EReference(eType=VariableBinding, lower=0, upper=-1, containment=False)
