import sys

from types import FunctionType

from pyecore.ecore import *
from pyecore.resources import ResourceSet, URI 

# Runtime state meta-metamodel
RuntimeStateElement = EClass("RuntimeStateElement")
RuntimeStateElement.eStructuralFeatures.append(EAttribute('name', EString))

RuntimeState = EClass("RuntimeState")
RuntimeState.eStructuralFeatures.append(EReference('elements', RuntimeStateElement, lower=0, upper=-1))

# Abstract syntax meta-metamodel evaluation
AbstractSyntaxOperation = EOperation('evaluate')
AbstractSyntaxOperation.eParameters.append(EParameter('runtime', eType=RuntimeState))

AbstractSyntaxElement = EClass("AbstractSyntaxElement")
AbstractSyntaxElement.eOperations.append(AbstractSyntaxOperation)

# Operational semantic meta-metamodel
# SemanticOperation = EClass("SemanticOperation")
# SemanticOperation.eStructuralFeatures.append(EReference('next', SemanticOperation, lower=0, upper=1))
# SemanticOperation.eStructuralFeatures.append(EReference('prev', SemanticOperation, lower=0, upper=1))

# SemanticOperation.eStructuralFeatures.append(EReference('syntax', AbstractSyntaxElement, lower=0, upper=1))
# SemanticOperation.eStructuralFeatures.append(EAttribute('callable',  EDataType("Callable", eType=FunctionType)))
# SemanticOperation.eStructuralFeatures.append(EReference('runtime', RuntimeState))

# Virtual machine definition
VirtualMachineStart = EOperation('start')
VirtualMachineStart.eParameters.append(EParameter('model', eType=AbstractSyntaxElement))
VirtualMachineStart.eParameters.append(EParameter('runtime', eType=RuntimeState))

VirtualMachinePause = EOperation('pause')
VirtualMachineSave = EOperation('restart')
VirtualMachineSave = EOperation('save')

VirtualMachineGetExpression = EOperation('get_expression')
VirtualMachineGetExpression.eParameters.append(EParameter('model', eType=AbstractSyntaxElement))
VirtualMachineGetExpression.eParameters.append(EParameter('runtime', eType=RuntimeState))
VirtualMachineGetExpression.eParameters.append(EParameter('expressions', eType=AbstractSyntaxElement))

ExpressionValuesAssociation = EClass('ExpressionValuesAssociation')
ExpressionValuesAssociation.eStructuralFeatures.append(EReference('expression', AbstractSyntaxElement, lower=0, upper=-1))
ExpressionValuesAssociation.eStructuralFeatures.append(EAttribute('value', EObject))

ExpressionValuesAssociations = EClass('ExpressionValuesAssociations')
ExpressionValuesAssociations.eStructuralFeatures.append(EReference('associations', AbstractSyntaxElement, lower=0, upper=-1))

VirtualMachineSetExpression = EOperation('set_expression')
VirtualMachineSetExpression.eParameters.append(EParameter('model', eType=AbstractSyntaxElement))
VirtualMachineSetExpression.eParameters.append(EParameter('runtime', eType=RuntimeState))
VirtualMachineSetExpression.eParameters.append(EParameter('expressions_values', eType=ExpressionValuesAssociations))

VirtualMachineChange = EOperation('change')
VirtualMachineChange.eParameters.append(EParameter('before', eType=AbstractSyntaxElement))
VirtualMachineChange.eParameters.append(EParameter('after', eType=AbstractSyntaxElement))

VirtualMachine = EClass("VirtualMachine")
VirtualMachine.eOperations.append(VirtualMachinePause)
VirtualMachine.eOperations.append(VirtualMachineSave)
VirtualMachine.eOperations.append(VirtualMachineGetExpression)
VirtualMachine.eOperations.append(VirtualMachineSetExpression)
VirtualMachine.eOperations.append(VirtualMachineChange)

Package = EPackage("LiveMetaMetaModel", nsURI="http://lipvm.org/LiveMetaMetaModel", nsPrefix="lipvm")
Package.eClassifiers.extend([
    RuntimeState,
    RuntimeStateElement,
    AbstractSyntaxElement,
    VirtualMachine
])

def main(arguments: list):
    if len(arguments) > 1:
        # Export ecore model at given path
        rset = ResourceSet()
        resource = rset.create_resource(URI(arguments[1]))
        resource.append(Package)
        resource.save()
    else:
        raise Exception("Please provide a path to export the .ecore model")

if __name__ == '__main__':
    main(sys.argv)
