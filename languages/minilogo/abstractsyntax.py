import sys

from pyecore.ecore import *
from pyecore.resources import ResourceSet, URI 

from core.metametamodel import *

Command = EClass('Command', abstract=True)
Command.eSuperTypes.append(AbstractSyntaxElement)

Operator = EEnum("Operator")
Operator.eLiterals.append(EEnumLiteral("PLUS"))
Operator.eLiterals.append(EEnumLiteral("MINUS"))
Operator.eLiterals.append(EEnumLiteral("DIVIDE"))
Operator.eLiterals.append(EEnumLiteral("MULTIPLY"))

Expression = EClass("Expression", abstract=True)
Expression.eSuperTypes.append(AbstractSyntaxElement)

BinaryExpression = EClass("BinaryExpression")
BinaryExpression.eSuperTypes.append(Expression)
BinaryExpression.eStructuralFeatures.append(EReference('left', Expression, lower=1, upper=1, containment=True))
BinaryExpression.eStructuralFeatures.append(EAttribute('operator', Operator))
BinaryExpression.eStructuralFeatures.append(EReference('right', Expression, lower=1, upper=1, containment=True))

ParenthesizedExpression = EClass("ParenthesizedExpression")
ParenthesizedExpression.eSuperTypes.append(Expression)
ParenthesizedExpression.eStructuralFeatures.append(EReference('expression', Expression, lower=1, upper=1, containment=True))

Terminal = EClass("Terminal")
Terminal.eSuperTypes.append(Expression)

Variable = EClass("Variable")
Variable.eSuperTypes.append(Terminal)
Variable.eStructuralFeatures.append(EAttribute('name', EString))

Literal = EClass("Literal")
Literal.eSuperTypes.append(Terminal)
Literal.eStructuralFeatures.append(EAttribute('value', EInt))

Assignment = EClass("Assignment")
Assignment.eSuperTypes.append(Command)
Assignment.eStructuralFeatures.append(EAttribute('variable_name', EString))
Assignment.eStructuralFeatures.append(EReference('expression', Expression, lower=1, upper=1, containment=True))

ColorCode = EClass('ColorCode')
ColorCode.eSuperTypes.append(AbstractSyntaxElement)
ColorCode.eStructuralFeatures.append(EAttribute('r', EInt, default_value=0))
ColorCode.eStructuralFeatures.append(EAttribute('g', EInt, default_value=0))
ColorCode.eStructuralFeatures.append(EAttribute('b', EInt, default_value=0))

Color = EClass("Color")
Color.eSuperTypes.append(Command)
Color.eStructuralFeatures.append(EReference('colorCode', ColorCode, lower=1, upper=1, containment=False))

Move = EClass("Move")
Move.eSuperTypes.append(Command)
Move.eStructuralFeatures.append(EReference('x', Expression, lower=1, upper=1, containment=True))
Move.eStructuralFeatures.append(EReference('y', Expression, lower=1, upper=1, containment=True))

PenStatus = EEnum("PenStatus")
PenStatus.eLiterals.append(EEnumLiteral("up"))
PenStatus.eLiterals.append(EEnumLiteral("down"))

Pen = EClass("Pen")
Pen.eSuperTypes.append(Command)
Pen.eStructuralFeatures.append(EAttribute('status', PenStatus))

Model = EClass('Model')
Model.eSuperTypes.append(AbstractSyntaxElement)
Model.eStructuralFeatures.append(EReference('commands', Command, lower=0, upper=-1, containment=True))

Coordinates = EClass('Coordinates')
Coordinates.eStructuralFeatures.append(EAttribute('x', EInt))
Coordinates.eStructuralFeatures.append(EAttribute('y', EInt))

Line = EClass('Line')
Line.eStructuralFeatures.append(EReference('color', ColorCode, lower=1, upper=1, containment=False))
Line.eStructuralFeatures.append(EReference('start', Coordinates, lower=1, upper=1, containment=False))
Line.eStructuralFeatures.append(EReference('end', Coordinates, lower=1, upper=1, containment=False))

Drawing = EClass('Drawing', superclass=RuntimeStateElement)
Drawing.eStructuralFeatures.append(EReference('lines', Line, lower=0, upper=-1, containment=True))

PenState = EClass('PenState', superclass=RuntimeStateElement)
PenState.eStructuralFeatures.append(EAttribute('status', PenStatus))
PenState.eStructuralFeatures.append(EReference('position', Coordinates, lower=1, upper=1, containment=False))
PenState.eStructuralFeatures.append(EReference('color', ColorCode, lower=1, upper=1, containment=False))

VariableBinding = EClass('VariableBinding')
VariableBinding.eStructuralFeatures.append(EAttribute('name', EString))
VariableBinding.eStructuralFeatures.append(EAttribute('value', EInt))

Scope = EClass('Scope', superclass=RuntimeStateElement)
Scope.eStructuralFeatures.append(EReference('bindings', VariableBinding, lower=0, upper=-1, containment=False))

AbstractSyntaxPackage = EPackage('AbstractSyntaxPackage', nsPrefix="minilogo", nsURI='http://minilogo.org/AbstractSyntaxPackage')
AbstractSyntaxPackage.eClassifiers.append(Model)
AbstractSyntaxPackage.eClassifiers.append(Command)
AbstractSyntaxPackage.eClassifiers.append(Assignment)
AbstractSyntaxPackage.eClassifiers.append(Color)
AbstractSyntaxPackage.eClassifiers.append(ColorCode)
AbstractSyntaxPackage.eClassifiers.append(Move)
AbstractSyntaxPackage.eClassifiers.append(Pen)
AbstractSyntaxPackage.eClassifiers.append(PenStatus)
AbstractSyntaxPackage.eClassifiers.append(VariableBinding)
AbstractSyntaxPackage.eClassifiers.append(Expression)
AbstractSyntaxPackage.eClassifiers.append(BinaryExpression)
AbstractSyntaxPackage.eClassifiers.append(ParenthesizedExpression)
AbstractSyntaxPackage.eClassifiers.append(Operator)
AbstractSyntaxPackage.eClassifiers.append(Terminal)
AbstractSyntaxPackage.eClassifiers.append(Variable)
AbstractSyntaxPackage.eClassifiers.append(Literal)

RuntimeStatePackage = EPackage('RuntimeStatePackage', nsPrefix="minilogo", nsURI='http://minilogo.org/RuntimeStatePackage')
RuntimeStatePackage.eClassifiers.append(Drawing)
RuntimeStatePackage.eClassifiers.append(Line)
RuntimeStatePackage.eClassifiers.append(Coordinates)
RuntimeStatePackage.eClassifiers.append(PenState)
RuntimeStatePackage.eClassifiers.append(Scope)

def main(arguments: list):
    if len(arguments) < 3:
        raise Exception("Please provide the path to store the .ecore abstract meta-metamodel")

    # Export ecore model at given path
    rset = ResourceSet()
    resource = rset.create_resource(URI(arguments[2]))
    resource.append(AbstractSyntaxPackage)
    resource.append(RuntimeStatePackage)
    resource.save()

if __name__ == '__main__':
    main(sys.argv)
