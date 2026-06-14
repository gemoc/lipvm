from functools import wraps
from typing import Any, LiteralString
from inspect import Parameter, signature


class OperationArguments:

    def __init__(self,  args: list = None, kwargs: dict = None,) -> OperationArguments:
        self._args = args if args is not None else []
        self._kwargs = kwargs if kwargs is not None else {}

    @property
    def positional(self) -> list:
        return self._args

    @property
    def keywords(self) -> dict:
        return self._kwargs

    def set_arg_at(self, index: int, value: Any) -> None:
        if len(self._args) > index:
            self._args[index] = value
        else:
            self._args.insert(index, value)

    def set_kw_arg(self, key: str, argument: Any) -> None:
        self._kwargs[key] = argument

class OperationVariables:

    def __init__(self, variables: dict = None) -> OperationVariables:
        object.__setattr__(self, "_vars",  variables if variables is not None else {})

    def __getattr__(self, attr_name: LiteralString) -> Any:
        if attr_name in self._vars:
            return self._vars[attr_name]
        raise Exception(f"{attr_name} not found in {self}")

    def __setattr__(self, attr_name: LiteralString, value: Any) -> None:
        self._vars[attr_name] = value

    @property
    def dictionary(self):
        return self._vars  

class Operation:

    def __init__(self, 
        function: callable, 
        arguments: OperationArguments = None, 
        variables: OperationVariables = None, 
        prev: Operation = None, 
        next: Operation = None) -> Operation:

        # Function wrapping
        self.args = arguments if arguments is not None else OperationArguments()
        self.vars = variables if variables is not None else OperationVariables()
        self.function = function

        # Operation chaining
        self.prev = prev
        self.next = next
        self.prev_result = None

    @property
    def function(self) -> callable:
        return self._function

    @function.setter
    def function(self, function: callable) -> None:
        self._function = function

         # Bind self instance to the _op parameter if present in function signature.
         # This will allow a function executed through an Operation to modify the chain of operations.
         # In other words, the execution can now modify itself.
        parameters = signature(self._function).parameters
        if "_op" in parameters:
            op_parameter = parameters["_op"]
            if op_parameter.kind == Parameter.KEYWORD_ONLY:
                self.args.set_kw_arg("_op", self)
            elif op_parameter.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD):
                self.args.set_arg_at(tuple(parameters).index("_op"), self)
            else:
                raise Exception(f"Unrecognized parameter kind {op_parameter.kind} for parameter \"_op\".")

    @property
    def head(self) -> Operation:
        """
        Returns: the first operation of the chain.
        """
        if self.has_prev:
            return self.prev.head
        return self

    @property
    def tail(self) -> Operation:
        """
        Returns: the last operation of the chain.
        """
        if self.has_next:
            return self.next.tail
        return self

    @property
    def has_prev(self) -> bool:
        return self.prev is not None

    @property
    def has_next(self) -> bool:
        return self.next is not None

    def before_put(self, operation: Operation) -> Operation:
        """
        Insert an operation in the chain, before the current one.
        Parameters:
             - operation : the operation to insert in the chain.
        Returns: the inserted operation
        """
        self.prev.next = operation
        operation.tail.next = self
        return operation

    def after_put(self, operation: Operation) -> Operation:
        """
        Insert an operation in the chain, after the current one.
        Parameters:
             - operation : the operation to insert in the chain.
        Returns: the inserted operation
        """
        if self.next:
            operation.next = self.next
        self.next = operation
        operation.prev = self
        return operation

    def execute(self) -> Any:
        """
        Executes the operation.
        If there was Any previous operation in the chain, inject the result of the operation into the scope of the next one.
        """
        result = self._function(*self.args.positional, **self.args.keywords)

        if self.next:
            self.next.prev_result = result

        return result
    
    def clone(self) -> Any:
        """
        Returns a new, unlinked Operation wrapping the same function.

        The clone shares its `args` and `vars` with the original (shallow copy)
        and has no `prev`/`next`, so it can be re-inserted elsewhere in a chain
        (e.g. to re-run a loop's condition on each iteration).
        """
        return Operation(self.function, arguments=self.args, variables=self.vars)


def operation(**functions):
    """
    This decorator can take Any number of arguments.
    Each arguments must take the following form:

    key = lambda arg1 arg2: something_that_returns_an_Operation()

    In this notation arg1 and arg2, must be identical to the
    arguments received by the decorated function.
    The wrapped function will be added to a chain of operation, after
    the result of the lambda.
    During execution the result of the operation returned by the lambda will be injected
    in the keyword argument (ex: key=None) that the decorated function must take.
    """
    def decorator(continuation):
        @wraps(continuation)
        def wrapper(*args, **kwargs):

            op_args = OperationArguments(args=args, kwargs=kwargs)

            def apply(f, key):
                def arguments(*a, **kw):
                    res = f(*a, **kw)
                    op_args.set_kw_arg(key, res)
                    return res
                return arguments

            chain = Operation(lambda: {})

            """
            Because functions are supposed to return operations to chain,
            we need to extract the function wrapped inside the operation (1 and 2)
            and wrap it again in another function (apply) that will add the result in the
            scope of the continuation during the execution.
            """
            for key in functions:
                op = functions[key](*args, **kwargs)   # 1
                function = op.function                 # 2
                op.function = apply(function, key)
                chain.tail.after_put(op)

            def continuation_handler(_op: Operation):
                """
                Handler added to the end of the chain in case language designer add the @opertion
                decorator to a method that already declare an operation. In that case we need to 
                add the returned operation to the chain during execution, otherwise, we propagate
                the function result.
                """
                if isinstance(_op.prev_result, Operation):
                    _op.after_put(_op.prev_result)
                else:
                    return _op.prev_result

            chain.tail.after_put(Operation(continuation, arguments=op_args))
            chain.tail.after_put(Operation(continuation_handler))

            return chain.next

        return wrapper
    return decorator

def loop(collection: list, function: callable, condition: Operation = None) -> Operation:
    """
    Creates a sequence of function calls with, in argument the items of a collection.

    Parameters:
         - collection: the collection of items to iterate over.
         - function: the function to call with each item of the collection in argument.
                      The function must return an Operation or use the @operation decorator.
         - condition: (optional) an Operation that acts as a repetition condition.
                      If this operation's result is True, the loop repeats.
                      If False, the loop terminates.

    Returns: the first Operation of the chain of operations.

    Note: When `condition` is provided, the loop implements conditional repetition:
          the body operations are executed repeatedly as long as the condition result
          is True. This enables while-loop semantics at the VM level.
    """
    chain = Operation(lambda: ())

    if not collection:
        return chain

    if condition is not None:
        # Build the conditional loop chain
        # We need to interleave: execute body -> check condition -> repeat or exit
        # Structure:
        #    [body_chain] -> [condition_check] -> (if True) -> [body_chain] -> ...
        #                            |
        #                        (if False) -> exit -> [body_chain] -> ...
        def repeat_or_exit(_op: Operation) -> None:
            if _op.prev_result:
                operation = _op
                for item in collection:
                    operation = operation.after_put(function(item))
                operation.after_put(condition.clone()).after_put(Operation(repeat_or_exit))

        # Attach the condition before the loop body
        chain.after_put(condition).after_put(Operation(repeat_or_exit))
    else:
        # Standard (unconditional) loop
        for item in collection:
            chain.tail.after_put(function(item))

    return chain.next


def if_then_else(condition_result: bool, then_collection: list, else_collection: list, function: callable) -> Operation:
    """
    Creates a sequence of function calls with, in argument, the items of either
    `then_collection` or `else_collection`, depending on `condition_result`.

    Parameters:
         - condition_result: the (already evaluated) result of the condition.
                              When True, `then_collection` is used, otherwise `else_collection` is used.
         - then_collection: the collection of items to iterate over when `condition_result` is True.
         - else_collection: the collection of items to iterate over when `condition_result` is False.
         - function: the function to call with each item of the chosen collection in argument.
                      The function must return an Operation or use the @operation decorator.

    Returns: the first Operation of the chain of operations.
    """
    collection = then_collection if condition_result else else_collection

    return loop(collection, function)
