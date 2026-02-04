from types import GeneratorType

from antlr4.RuleContext import RuleContext
from antlr4.tree.Tree import ParseTreeVisitor

from backend.parser import Parser

class Environment:
    """
    Environment for interpreting a program.
    Language designer can dynamically set the attributes they need to keep track of.

    Example:
    - self._environment.attribute = value
    """

    # Making explicit the fact we use reflectivity to set the attributes of the environment (for debugging)
    def __setattr__(self, name, value):
        super().__setattr__(name, value)

    def __getattr__(self, name):
        return super().__getattribute__(name)

class Visit:

    def __init__(self, tree: RuleContext):
        self._tree = tree

    @property
    def tree(self):
        return self._tree


class Interpreter(ParseTreeVisitor):
    """
    AST visitor to extend in order to define the interpretation of a program.

    The interpreter requires the language designers to use Python generators through:
    - The yield keyword when visiting a subtree: yield self.visit(tree), yield self.visitChildren(tree).
    - The yield keyword instead of standard return when defining a method's return value.

    This allows the methods of the visitor to be converted into generators when they depend on the visit of a subtree.
    Thanks to this, in the self._interpretation_step() method, the recursion stack can be made explicit.
    I.e. when calling a visit<NodeName> method, either the return value is a generator of value, or a literal value.
    Chains of generators are therefore representing the recursion stack.

    This allows to walk the AST in an iterative manner, while keeping the recursive style.
    Ultimately it is resistant to stack overflows and frees us from the need to manage threads to control the recursion.

    Credits:
    - https://medium.com/@touahartoufik/implementing-the-visitor-pattern-without-recursion-with-python-90a136de1f2f
    """

    def __init__(self, parser: Parser):
        """
        Constructor.

        :param parser: an instance of Parser class
        """
        self._environment = Environment()
        self._parser = parser

        self._interpretation_stack = []
        self._interpretation_result = None
        self._interpretation_steps = []

        self._halt = False

    def visit(self, tree):
        """
        Mark a node to visit by the interpretation loop.
        :param tree: the AST to be visited
        """
        return Visit(tree)

    def interpret(self, code: str):
        tree = self._parser.parse(code)
        self._interpretation_stack = [self.visit(tree)]
        self._interpretation_result = None
        self._interpretation()

    def _interpretation(self):
        while self._interpretation_stack and not self._halt:
            self._interpretation_step()

    def _interpretation_step(self):
        while self._interpretation_stack and not self._halt:
            try:
                current = self._interpretation_stack[-1]
                if isinstance(current, GeneratorType):
                    self._interpretation_stack.append(current.send(self._interpretation_result))
                    self._interpretation_result = None
                elif isinstance(current, Visit):
                    result = self._interpretation_stack.pop().tree.accept(self)
                    self._interpretation_stack.append(result)
                    if hasattr(current.tree, "stepNode"):
                        self._interpretation_steps.append(result)
                else:
                    self._interpretation_result = self._interpretation_stack.pop()
            except StopIteration:  # In case of return (last yield instruction)
                if self._should_end_step(self._interpretation_stack.pop()):
                    self._interpretation_steps.pop()
                    break # Reached the end of a step

    def _should_end_step(self, result):
        return self._interpretation_steps and self._interpretation_steps[-1] == result

    def visitChildren(self, node):
        """
        Recursively visit the children of an AST node.

        :param node: the parent node of which to visit the children
        :return: a list containing the results of the visit of the children
        """
        n = node.getChildCount()
        for i in range(n):
            c = node.getChild(i)
            if isinstance(c, RuleContext):
                yield self.visit(c)

    def halt(self):
        self._halt = True

    def proceed(self):
        self._halt = False
        self._interpretation()

    def step(self):
        self._halt = False
        self._interpretation_step()

    @property
    def environment(self):
        return self._environment