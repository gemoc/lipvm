from antlr4.ParserRuleContext import ParserRuleContext

from threading import Thread, Event

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

class Interpreter:
    """
    Interpreter for executing a program.
    The interpreter controls the execution using a semaphore and a thread.
    """

    EXECUTION_INTERRUPTED = Event()

    def __init__(self, parser: Parser, visitor_class):
        """
        Constructor.

        :param parser: an instance of Parser class
        :param visitor_class: a LanguageVisitor class to instantiate
        """
        self._environment = Environment()

        self._execution = Event()            # Semaphore for controlling the execution
        self._execution.set()                # Semaphore unlocked by default

        self._step = Event()                 # Semaphore for controlling the stepping operation
        self._step.set()                     # Semaphore unlocked by default

        self._parser = parser
        self._visitor = visitor_class(self)


    def visit(self, tree):
        """
        Recursively visit the tree node of a program's AST.

        :param tree: the AST to be visited
        :return: TODO: Return value not yet determined
        """
        self._execution.wait()               # Stop the execution until proceed or step command
        result = tree.accept(self._visitor)
        if hasattr(tree, "stepNode"):
            if not self._step.is_set() and self._execution.is_set():
                Interpreter.EXECUTION_INTERRUPTED.set()
            self._step.wait()
        return result


    def visitChildren(self, node):
        """
        Recursively visit the children of an AST node.

        :param node: the parent node of which to visit the children
        :return: a list containing the results of the visit of the children
        """
        results = []
        n = node.getChildCount()
        for i in range(n):
            c = node.getChild(i)
            if isinstance(c, ParserRuleContext):
                results.append(self.visit(c))
        return results


    def async_interpret(self, code: str):
        """
        Interpret the given tree and return the result.
        The execution is performed asynchronously, to synchronize your thread, use:

        - Interpreter.EXECUTION_HALT.wait()
        - Interpreter.EXECUTION_FINISHED.wait()

        :param code: the source code to interpret.
        :return: a thread within which the execution takes place.
        """
        tree = self._parser.parse(code)

        self._thread = Thread(target = self._execute, args = (tree,))
        self._thread.start()


    def isRunning(self):
        return self._thread.is_alive()


    def interpret(self, code: str) -> Environment:
        self.async_interpret(code)
        Interpreter.EXECUTION_INTERRUPTED.wait()
        return self._environment


    def _execute(self, tree):
        Interpreter.EXECUTION_INTERRUPTED.clear()
        self.visit(tree)
        Interpreter.EXECUTION_INTERRUPTED.set()


    def halt(self):
        if not self.isRunning():
            raise Exception("No running execution, cannot halt.")
        self._execution.clear()                      # Lock the execution
        Interpreter.EXECUTION_INTERRUPTED.set()      # Unlock the EXECUTION_HALT semaphore


    def async_proceed(self):
        if not self.isRunning():
            raise Exception("No execution to proceed on.")
        Interpreter.EXECUTION_INTERRUPTED.clear()    # Lock again the EXECUTION_HALT semaphore
        self._step.set()                             # Remove the step lock
        self._execution.set()                        # Unlock the execution


    def proceed(self) -> Environment:
        self.async_proceed()
        Interpreter.EXECUTION_INTERRUPTED.wait()
        return self._environment


    def async_step(self):
        if not self.isRunning():
            raise Exception("No execution to step on.")
        Interpreter.EXECUTION_INTERRUPTED.clear()
        self._step.set()                             # Unlock previous step
        self._step.clear()                           # Get ready to lock again
        self._execution.set()                        # Unlock the execution


    def step(self) -> Environment:
        self.async_step()
        Interpreter.EXECUTION_INTERRUPTED.wait()
        return self._environment


    @property
    def environment(self):
        return self._environment