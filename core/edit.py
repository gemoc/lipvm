from __future__ import annotations

from pyecore.ecore import *

from core.language import AbstractSyntaxElement, RuntimeState


class EditSyntaxOperation(EObject, metaclass=MetaEClass):
    """
    Base class for any operation in an edit script.
    """
    abstract = True

    # The identifier of the node to edit
    identifier = EAttribute(eType=EInt)

    # The AbstractSyntaxElement to which refers this operation (set by EditScript.attach_to)
    syntax = EReference(eType=AbstractSyntaxElement, lower=0, upper=1)

    def _raise_if_invalid_syntax(self) -> None:
        if self.syntax is None:
            raise Exception(f"The syntax element for identifier {self.identifier} was not resolved yet.")
        if self.identifier != self.syntax.identifier:
            raise Exception(f"The syntax element to edit does not match with current edit operation, expecting identifier: {self.identifier}.")

    def prepare(self, runtime: RuntimeState) -> None:
        self._raise_if_invalid_syntax()
        if self.syntax.prepare_migration is not None:
            self.syntax.prepare_migration.evaluate(runtime)

    def migrate(self, runtime: RuntimeState) -> None:
        self._raise_if_invalid_syntax()
        if self.syntax.perform_migration is not None:
            self.syntax.perform_migration.evaluate(runtime)

    def apply(self) -> None:
        self._raise_if_invalid_syntax()
        self.edit_syntax(self.syntax)

    def edit_syntax(self, syntax: AbstractSyntaxElement) -> None:
        raise NotImplementedError("Please Implement this method")


class InsertSyntaxOperation(EditSyntaxOperation, metaclass=MetaEClass):
    """
    Represents adding a new node as a child of a target parent.
    """

    # The index in the collection of children at which to insert the new element.
    index = EAttribute(eType=EInt)

    # The new element to insert
    element = EReference(eType=EObject, lower=1, upper=1)

    def edit_syntax(self, syntax: AbstractSyntaxElement) -> None:
        syntax.add_child(self.index, self.element)


class UpdateSyntaxOperation(EditSyntaxOperation, metaclass=MetaEClass):
    """
    Represents changing an attribute or reference of an existing node.
    """

    # The name of the attribute to change
    attribute_name = EAttribute(eType=EString)

    # The new value for this attribute, can be an EInt, EString...
    element = EReference(eType=EObject, lower=1, upper=1)

    def edit_syntax(self, syntax: AbstractSyntaxElement) -> None:
        syntax.set_attribute(self.attribute_name, self.element)


class DeleteSyntaxOperation(EditSyntaxOperation, metaclass=MetaEClass):
    """
    Represents removing an existing node from its parent.
    """

    # The index of the child to remove in the collection of children.
    index = EAttribute(eType=EInt)

    def edit_syntax(self, syntax: AbstractSyntaxElement) -> None:
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
            for op in op_map[syntax.identifier]:
               op.syntax = syntax

        # Recursively check children to ensure all nodes are processed.
        for child in syntax.get_children():
            self.attach_to(child)

    def prepare(self, runtime: RuntimeState) -> None:
        for edit in self.operations:
            edit.prepare(runtime)

    def apply(self) -> None:
        for edit in self.operations:
            edit.apply()

    def migrate(self, runtime: RuntimeState) -> None:
        for edit in self.operations:
            edit.migrate(runtime)
