import pytest
from pyecore.ecore import MetaEClass, EReference

from core.language import AbstractSyntaxElement, RuntimeStateElement
from core.operation import Operation, operation


# --- Test doubles ---

class _Node(AbstractSyntaxElement, metaclass=MetaEClass):
    """A plain AST element."""
    pass


class _BackedElement(RuntimeStateElement, metaclass=MetaEClass):
    """A runtime element that stands in for an AST construct and declares it."""
    definition = EReference(eType=AbstractSyntaxElement, lower=0, upper=1)

    def ast_node(self) -> AbstractSyntaxElement:
        return self.definition


class _BareElement(RuntimeStateElement, metaclass=MetaEClass):
    """A runtime element that does NOT declare an AST node (ast_node() -> None)."""
    pass


# --- Resolution contract: Operation.syntax_element ---

def test_ast_element_arg_resolves_itself():
    node = _Node(identifier=1)
    assert Operation(lambda *a: None, args=(node, object())).syntax_element is node


def test_backed_runtime_element_resolves_its_ast_node():
    node = _Node(identifier=1)
    element = _BackedElement(name="e", definition=node)
    # The subject is a runtime element, not an AST element, yet it resolves.
    assert Operation(lambda *a: None, args=(element, object())).syntax_element is node


def test_bare_runtime_element_resolves_none():
    element = _BareElement(name="e")
    assert Operation(lambda *a: None, args=(element, object())).syntax_element is None


def test_backed_element_with_unset_definition_resolves_none():
    element = _BackedElement(name="e")  # definition left unset
    assert Operation(lambda *a: None, args=(element, object())).syntax_element is None


# --- Enforcement: a stepped @operation must relate to an AST element ---

def test_stepped_operation_on_ast_element_is_allowed():
    class _AstStep(AbstractSyntaxElement, metaclass=MetaEClass):
        @operation(is_step=True)
        def evaluate(self, runtime):
            return None

    _AstStep(identifier=1).evaluate(object())  # no raise


def test_stepped_operation_on_backed_runtime_element_is_allowed():
    node = _Node(identifier=1)

    class _BackedStep(RuntimeStateElement, metaclass=MetaEClass):
        definition = EReference(eType=AbstractSyntaxElement, lower=0, upper=1)

        def ast_node(self):
            return self.definition

        @operation(is_step=True)
        def evaluate(self, runtime):
            return None

    _BackedStep(name="s", definition=node).evaluate(object())  # no raise


def test_stepped_operation_without_ast_node_raises():
    class _BareStep(RuntimeStateElement, metaclass=MetaEClass):
        @operation(is_step=True)
        def evaluate(self, runtime):
            return None

    with pytest.raises(TypeError, match="stepped @operation must relate to an AST element"):
        _BareStep(name="s").evaluate(object())


def test_non_stepped_operation_without_ast_node_is_allowed():
    class _BarePlain(RuntimeStateElement, metaclass=MetaEClass):
        @operation
        def evaluate(self, runtime):
            return None

    _BarePlain(name="s").evaluate(object())  # no raise -- only is_step is enforced


# --- The sysmlv2 element implements the contract via its `definition` ---

def test_sysmlv2_element_definition_implements_contract():
    from languages.sysmlv2.runtime import ExecutableStateUsage
    from languages.sysmlv2.syntax import Package

    ast = Package(declaredName="P")
    usage = ExecutableStateUsage(name="m", qualified_name="M::m", definition=ast)
    assert usage.ast_node() is ast
    assert Operation(lambda *a: None, args=(usage, object())).syntax_element is ast
