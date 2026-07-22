from typing import Callable, Any
from functools import wraps

class Operation:

    def __init__(self,
        function: Callable = None,
        continuation: Operation = None,
        args: tuple = None,
        kwargs: dict = None,
        receives_result: bool = False) -> Operation:

        self.function = function
        self.continuation = continuation
        self.receives_result = receives_result

        self.args = args if args is not None else ()
        self.kwargs = kwargs if kwargs is not None else {}

    @property
    def syntax_element(self):
        from core.language import AbstractSyntaxElement
        for arg in self.args:
            if isinstance(arg, AbstractSyntaxElement):
                return arg
        return None

    @property
    def has_continuation(self) -> bool:
        return self.continuation is not None
    
    @property
    def has_syntax(self) -> bool:
        return self.syntax_element is not None
    
    def append(self, continuation: Operation) -> None:
        last = self
        while last.has_continuation:
            last = last.continuation
        last.continuation = continuation

    def execute(self) -> Any:
        result = self.function(*self.args, **self.kwargs)

        if isinstance(result, Operation):
            # The function produced a sub-chain: splice it in so execution
            # flows through it before resuming with the current successor.
            result.append(self.continuation)
            self.continuation = result
        elif self.has_continuation and self.continuation.receives_result:
            self.continuation.args = (result,)

        return result


def operation(_method: Callable = None, **sub_operations_dict: Callable) -> Callable:
    """Decorator that turns an `evaluate` method into a deferred Operation.

    Used as `@operation`, calling the method captures its arguments and returns
    an Operation without running the body. The body only runs when the VM steps
    through that Operation.

    Used as `@operation(left=..., right=...)`, each keyword argument is an
    evaluator for a sub-expression: a callable with the same signature as 
    the decorated method. Those sub-expressions are evaluated lazily and their 
    results are injected as keyword arguments into the method body before it runs. 
    This makes it possible to write:

        @operation(
            left=lambda self, runtime: self.left.evaluate(runtime),
            right=lambda self, runtime: self.right.evaluate(runtime),
        )
        def evaluate(self, runtime, left=None, right=None):
            return left + right

    Because evaluators are called lazily at execution time, a hot-swap that
    replaces a sub-node before its evaluator runs will be picked up naturally.
    """
    def decorator(method: Callable) -> Callable:
        @wraps(method)
        def wrapper(*args, **kwargs) -> Operation:
            operation = Operation(method, args=args, kwargs=dict(kwargs))

            if not sub_operations_dict:
                return operation

            sub_operations = list(sub_operations_dict.items())

            def iterate(index: int = 0) -> Operation:
                if index >= len(sub_operations):
                    return operation
                
                key, evaluator = sub_operations[index]

                def inject(result) -> None:
                    operation.kwargs[key] = result

                sub = evaluator(*args)
                sub.append(Operation(inject, receives_result=True))
                sub.append(Operation(iterate, args=(index + 1,)))
                return sub

            return Operation(iterate)
        return wrapper

    if _method is not None:
        return decorator(_method)
    return decorator


def lazy_loop(collection: list, function: Callable, args: tuple = ()) -> Operation:
    """Build a chain of operations from a collection, one item at a time.

    Each item's Operation is only created when the VM actually reaches it, not
    all at once upfront. This keeps memory low and makes hot-swapping safe: if
    the collection changes before an item is reached, the new version is used.

    `function` is called as `function(item, *args)` to produce each Operation.

    Without `condition`, the chain runs through every item once and stops.

    With `condition`, the whole collection repeats as long as `condition`
    evaluates to True. Each time the condition is checked and passes, a fresh
    pass over the collection is built and spliced in. When the condition fails,
    execution moves on.
    """
    if not collection:
        return None

    def iterate(index: int = 0) -> Operation:
        if index >= len(collection):
            return None
        element = function(collection[index], *args)
        element.append(Operation(iterate, args=(index + 1,)))
        return element

    #if condition is None:
    #    return Operation(iterate)

    #def apply(repeat: bool) -> Operation:
        # On repeat, yield a new body followed by the condition check returned by the recursive call.
        # Operation.execute() will splice it in front of the loop's continuation.
    #    if repeat:
    #        chain = Operation(iterate)
    #        chain.append(lazy_loop(collection, function, condition, args))
    #        return chain
    #    return None

    #condition.continuation = Operation(apply, receives_result=True)
    return Operation(iterate)

def lazy_while(function: Callable, condition: Operation, args: tuple = ()) -> Operation:

    def apply(repeat: bool) -> Operation:
        # On repeat, yield a new body followed by the condition check returned by the recursive call.
        # Operation.execute() will splice it in front of the loop's continuation.
        if repeat:
            chain = function(*args)
            chain.append(lazy_while(function, condition, args))
            return chain
        return None

    condition.continuation = Operation(apply, receives_result=True) 
    return condition


def if_then_else(condition_result: bool, then_collection: list, else_collection: list, function: Callable, args: tuple = ()) -> Operation:
    """Build a chain for one of two branches based on an already-evaluated condition.

    Picks `then_collection` when `condition_result` is True, `else_collection`
    otherwise, then delegates to `lazy_loop` to build the chain lazily.
    """
    collection = then_collection if condition_result else else_collection

    return lazy_loop(collection, function, args=args)
