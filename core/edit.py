from __future__ import annotations

from typing import TYPE_CHECKING

from pyecore.ecore import *

if TYPE_CHECKING:
    from core.language import AbstractSyntaxElement

class EditSyntaxOperation(EObject, metaclass=MetaEClass):
    """
    Base class for any operation in an edit script.
    """
    abstract = True
    
    # The identifier of the node to edit
    identifier = EAttribute(eType=EInt)

    def apply(self, syntax: AbstractSyntaxElement) -> None:
        if  self.identifier != syntax.identifier:
            raise Exception("The syntax element to edit does not match with current edit operation, expecting identifier: " + str(self.identifier))

class InsertSyntaxOperation(EditSyntaxOperation, metaclass=MetaEClass):
    """
    Represents adding a new node as a child of a target parent.
    """

    # The index in the collection of children at which to insert the new element.
    index = EAttribute(eType=EInt)

    # The new element to insert
    element = EReference(eType=EObject, lower=1, upper=1)

    def apply(self, syntax: AbstractSyntaxElement) -> None:
        super().apply(syntax)
        syntax.add_child(self.index, self.element)

class UpdateSyntaxOperation(EditSyntaxOperation, metaclass=MetaEClass):
    """
    Represents changing an attribute or reference of an existing node.
    """

    # The name of the attribute to change
    attribute_name = EAttribute(eType=EString)
    
    # The new value for this attribute, can be an EInt, EString...
    element = EReference(eType=EObject, lower=1, upper=1)

    def apply(self, syntax: AbstractSyntaxElement) -> None:
        super().apply(syntax)
        syntax.set_attribute(self.attribute_name, self.element)


class DeleteSyntaxOperation(EditSyntaxOperation, metaclass=MetaEClass):
    """
    Represents removing an existing node from its parent.
    """

    # The index of the child to remove in the collection of children.
    index = EAttribute(eType=EInt)

    def apply(self, syntax: AbstractSyntaxElement) -> None:
        super().apply(syntax)
        syntax.del_child_at(self.index)
    
class EditScript(EObject, metaclass=MetaEClass):
    """
    A script containing a sequence of operations to transform an AbstractSyntaxElement tree.
    """

    # The ordered list of operations to execute
    operations = EReference(eType=EditSyntaxOperation, lower=0, upper=-1)
    
    def add_operation(self, operation: EditSyntaxOperation) -> None:
        self.operations.append(operation)
        

    def attach_to(self, syntax: AbstractSyntaxElement) -> None:
        """
        Visits the AbstractSyntaxElement tree and adds to the edit_operations
        collection of nodes whose identifier matches one or more operations
        in this script.
        """

        # Build lookup dictionary if not already built for this attach sequence.
        # Using a dictionary allows for O(1) lookup instead of iterating all operations per node.
        # This reduces complexity from O(N*M) to O(N+M).
        if not hasattr(self, '_op_map_cache'):
            self._op_map_cache = {}
            for op in self.operations:
                self._op_map_cache.setdefault(op.identifier, []).append(op)

        op_map = self._op_map_cache

        if syntax.identifier in op_map:
            syntax.edit_operations.extend(op_map[syntax.identifier])

        # Recursively check children to ensure all nodes are processed.
        for child in syntax.get_children():
            self.attach_to(child)
        