from typing import Callable, Generator

from antlr4.ParserRuleContext import ParserRuleContext
from antlr4.tree.Tree import ParseTreeVisitor

from backend.parser import Parser
from backend.environment import Environment

class Visit:

    def __init__(self, tree: ParserRuleContext):
        self._tree = tree

    @property
    def tree(self) -> ParserRuleContext:
        return self._tree

class Signal:

    def __init__(self, handler: Callable[[Interpreter], None] = None):
        self._handler = handler

    @property
    def handler(self):
        return self._handler

class Halt(Signal):
    pass

class Step(Signal):
    pass

class SignalBeginStep(Step):
    
    def __init__(self, handler: Callable[[Interpreter], None] = None):
        if handler is None:
            super().__init__(lambda: print("Begin step"))
        else:
            super().__init__(handler)
    
class SignalEndStep(Step):

    def __init__(self, handler: Callable[[Interpreter], None] = None):
        if handler is None:
            super().__init__(lambda: print("End step"))
        else:
            super().__init__(handler)

def step(visit_method):
    """
    Function to use as a decorator for visit methods in a LanguageInterpreter class.
    :param visit_method: a visit method decorated with @step.
    :return: a wrapper function that annotates the node in argument to add the stepNode = True attribute.
    """
    def wrapper(*args, **kwargs):
        yield args[0].signalBeginStep()
        result = yield visit_method(*args, **kwargs)
        yield args[0].signalEndStep()
        return result
    return wrapper


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
        self._parser = parser

        # Interpretation related variables 
        self._environment = Environment()
        self._tree = None

        self._interpretation_stack = []
        self._interpretation_result = None

    def visit(self, tree: ParserRuleContext) -> Visit:
        """
        Mark a node to visit by the interpretation loop.

        :param tree: the AST to be visited
        """
        return Visit(tree)

    def _interpretation(self) -> None:
        proceed = True
        while self._interpretation_stack and proceed:
            proceed = self._interpretation_step()

    def _interpretation_step(self) -> bool:
        proceed = True
        while self._interpretation_stack and proceed:
            try:
                current = self._interpretation_stack[-1]
                if isinstance(current, Generator):
                    self._interpretation_stack.append(current.send(self._interpretation_result))
                    self._interpretation_result = None
                elif isinstance(current, Visit):
                    self._interpretation_stack.pop()
                    result = current.tree.accept(self)
                    self._interpretation_stack.append(result)
                elif isinstance(current, Signal):
                    self._interpretation_stack.pop()
                    if isinstance(current, Halt):
                        return False
                    elif isinstance(current, Step):
                        proceed = False
                    if current.handler is not None:
                        current.handler()
                else:
                    self._interpretation_result = self._interpretation_stack.pop()
            except StopIteration:  # In case of return (last yield instruction)
                self._interpretation_stack.pop()
        return True

    def visitChildren(self, node: ParserRuleContext) -> Generator[ParserRuleContext, None, None]:
        """
        Recursively visit the children of an AST node.

        :param node: the parent node of which to visit the children
        :return: a sequence of generators
        """
        results = []
        n = node.getChildCount()
        for i in range(n):
            c = node.getChild(i)
            if isinstance(c, ParserRuleContext):
                result = yield self.visit(c)
                results.append(result)
        yield results

    def interpret(self, code: str) -> None:
        # Set the interpretation environment
        self._environment = Environment()
        self.initialize()

        # Set the code to interpret
        self._tree = self._parser.parse(code)

        # Initialize the state of the interpretation
        self._interpretation_stack = [self.visit(self._tree)]
        self._interpretation_result = None

        # Start the interpretation loop
        self._interpretation()

    def initialize(self) -> None:
        raise Exception("Implement this method to initialize the interpretation.")    

    # Halt and step commands to use from external code.
    def halt(self) -> Halt:
        self._interpretation_stack.append(Halt())

    def proceed(self) -> None:
        self._interpretation()

    def step(self) -> None:
        self._interpretation_step()

    # Halt and step commands to use from the interpreter subclasses.
    # Ex: yield signalHalt()

    def signalHalt(self) -> Halt:
        return Halt()

    def signalBeginStep(self, handler: Callable = None) -> SignalBeginStep:
        return SignalBeginStep(handler)

    def signalEndStep(self, handler: Callable = None) -> SignalEndStep:
        return SignalEndStep(handler)

    @property
    def environment(self) -> Environment:
        return self._environment

    @property
    def tree(self) -> ParserRuleContext:
        return self._tree

    @property
    def parser(self) -> Parser:
        return self._parser
