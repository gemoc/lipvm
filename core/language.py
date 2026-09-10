from __future__ import annotations

from typing import Any, LiteralString, List, Tuple

from pyecore.ecore import *

from core.operation import Operation

# --- Helpers ---

# This helper allows the pythonic usage of Ecore to use the keyword notation
# when instanciating model elements, similarly to the default pyEcore style.
# E.g. ModelElement(key=value)
def _eobject_init(self, **kwargs) -> None:
    for name, value in kwargs.items():
        setattr(self, name, value)

EObject.__init__ = _eobject_init


class RuntimeStateElement(EObject, metaclass=MetaEClass):

    name = EAttribute(eType=EString)

    def ast_node(self) -> "AbstractSyntaxElement | None":
        """The AST element this runtime element executes on behalf of, if any.

        Defaults to None. A runtime element that stands in for an AST construct
        -- and can therefore be the subject of a stepped Operation (e.g. a
        sysmlv2 ExecutableStateUsage) -- overrides this to return that construct,
        so Operation.syntax_element can relate the operation to the AST node.
        """
        return None


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


class AbstractSyntaxElement(EObject, metaclass=MetaEClass):

    abstract = True

    identifier = EAttribute(eType=ELong)

    text_position = EReference(eType=ASTElementPosition, lower=0, upper=1)


    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)


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
            if index <= count + size:
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

    def isUpdatePoint(self) -> bool:
        return False

    def evaluate(self, runtime: RuntimeState) -> Operation | None:
        raise NotImplementedError("Please Implement this method")


class UpdatePoint(AbstractSyntaxElement, metaclass=MetaEClass):
    """An AST node marked as a checkpoint: a place where, while the program
    runs, the VM may take a pending Update into account (see core.edit.Update).
    A language engineer marks a node type as a checkpoint by extending
    UpdateBeforePoint or UpdateAfterPoint; the VM applies an Update only when
    the running operation's node is an update point whose type matches the
    Update's declared checkpoint_type().
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def isUpdatePoint(self) -> bool:
        return True

    def isUpdateBefore(self) -> bool:
        raise NotImplementedError("Abstract class, please use UpdateBeforePoint or UpdateAfterPoint")

    def isUpdateAfter(self) -> bool:
        raise NotImplementedError("Abstract class, please use UpdateBeforePoint or UpdateAfterPoint")

class UpdateBeforePoint(UpdatePoint, metaclass=MetaEClass):

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def isUpdateBefore(self) -> bool:
        return True

    def isUpdateAfter(self) -> bool:
        return False

class UpdateAfterPoint(UpdatePoint, metaclass=MetaEClass):

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def isUpdateBefore(self) -> bool:
        return False

    def isUpdateAfter(self) -> bool:
        return True


class Scenario(AbstractSyntaxElement, metaclass=MetaEClass):

    # Program declarative syntax elements,
    # e.g functions, classes, FSM states etc
    program_definition = EReference(eType=AbstractSyntaxElement, lower=0, upper=1)

    # Program execution commands,
    # e.g. function calls, FSM transitions activations etc
    program_command = EReference(eType=AbstractSyntaxElement, lower=0, upper=1)


    def init(self, runtime: RuntimeState = None) -> Operation:

        if runtime is None:
            runtime = RuntimeState()

        operation = self.program_definition.evaluate(runtime)

        if self.program_command is not None:
            operation.continuation = self.program_command.evaluate(runtime)

        return operation
