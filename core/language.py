from __future__ import annotations

from typing import Any, LiteralString, List, Tuple

from pyecore.ecore import *

from core.edit import EditSyntaxOperation

# Statically defined EClasses (declared as plain Python classes with the
# MetaEClass metaclass) do not get the kwargs-to-attributes constructor that
# pyecore generates for dynamically defined EClasses. Patch EObject so that
# `SomeEObjectSubclass(attr=value, ...)` works the same way for both.
def _eobject_init(self, **kwargs) -> None:
    for name, value in kwargs.items():
        setattr(self, name, value)

EObject.__init__ = _eobject_init

# Runtime state meta-metamodel
class RuntimeStateElement(EObject, metaclass=MetaEClass):
    name = EAttribute(eType=EString)

class RuntimeState(EObject, metaclass=MetaEClass):

    elements = EReference(eType=RuntimeStateElement, lower=0, upper=-1)

    def __getattr__(self, attr_name: LiteralString) -> Any:
        for element in self.elements:
            if element.name == attr_name:
                return element
        raise Exception(attr_name + " not found in RuntimeState")

class ASTElementPosition(EObject, metaclass=MetaEClass):
    
    start_line = EAttribute(eType=EInt, default_value=-1)
    start_column = EAttribute(eType=EInt, default_value=-1)
    end_line = EAttribute(eType=EInt, default_value=-1)
    end_column = EAttribute(eType=EInt, default_value=-1)

class SafepointCondition(EObject, metaclass=MetaEClass):

    def evaluate(self, runtime: RuntimeState):
        raise NotImplementedError("Please Implement this method")

# Abstract syntax meta-metamodel
class AbstractSyntaxElement(EObject, metaclass=MetaEClass):
    abstract = True

    identifier = EAttribute(eType=ELong)

    position = EReference(eType=ASTElementPosition, lower=0, upper=1)

    edit_operations = EReference(eType=EditSyntaxOperation, lower=0, upper=-1)

    safepoint_condition = EReference(eType=SafepointCondition, lower=0, upper=1)

    def set_attribute(self, name: str, value: EObject) -> None:
        setattr(self, name, value)

    def get_attributes(self) -> List[Tuple[LiteralString, Any]]:
        attributes = []
        for feature in self.eClass.eAttributes:
            attributes.append((feature.name, self.eGet(feature)))
        return attributes

    def __get_children_features(self) -> List[EStructuralFeature]:
        features = []
        for feature in self.eClass.eReferences:
            if issubclass(feature.eType.python_class, AbstractSyntaxElement):
                features.append(feature)
        return features

    def __get_children_feature_at(self, index: int) -> Tuple[int, EStructuralFeature]:
        count = 0
        for feature in self.__get_children_features():
            size = len(self.eGet(feature)) if feature.many else 1
            if index <= count + size: # <= instead of < allows add_child to add a child to the last supported feature 
                return (index - count, feature)
            count += size
        raise Exception(f"Feature for children index: {index} not found.")

    def get_children(self) -> List[AbstractSyntaxElement]:
        children = []
        for feature in self.__get_children_features():
            if feature.many:
                values = self.__getattribute__(feature.name)
            else:
                values = [self.__getattribute__(feature.name)]
            children.extend((x for x in values if x))
        return children
    
    def get_child_at(self, index: int) -> AbstractSyntaxElement:
        offset, feature = self.__get_children_feature_at(index)
        value = self.eGet(feature)        
        if feature.many:
            return value[offset] if offset < len(value) else None
        return value

    def add_child(self, index: int, child: AbstractSyntaxElement) -> None:
        offset, feature = self.__get_children_feature_at(index)
        if feature.many:
            self.eGet(feature).insert(offset, child)
        else:
            self.eSet(feature, child)

    def del_child_at(self, index: int) -> None:
        offset, feature = self.__get_children_feature_at(index)
        if feature.many:
            self.eGet(feature).pop(offset)
        else:
            self.eSet(feature, None)

    def evaluate(self, runtime: RuntimeState) -> None:
        raise NotImplementedError("Please Implement this method")

    def apply_edit_operations(self) -> AbstractSyntaxElement:
        # Copy current node
        node = self.__class__()
        for feature in self.eClass.eAllStructuralFeatures():
            if feature.name == "edit_operations":
                continue
            value = self.eGet(feature)
            node.eSet(feature, list(value) if feature.many else value)

        # Apply the changes to the copy
        for edit_operation in self.edit_operations:
            edit_operation.apply(node)

        return node

