from functools import wraps

class Scope:
    
    def __init__(self, args: list = [], kwargs: dict = {}, prev_result: any = None) -> Scope:
        self._args = args
        self._kwargs = kwargs
        self._prev_result = prev_result
    
    @property
    def args(self) -> list:
        return self._args
    
    @property
    def kwargs(self) -> dict:
        return self._kwargs
    
    @property
    def prev_result(self) -> any:
        return self._prev_result

    def add_kw_arg(self, key, argument)  -> None:
        self._kwargs[key] = argument

class Operation:

    def __init__(self, function: callable, scope: Scope = Scope(), prev = None, next=None) -> Operation:
        
        # Function wrapping
        self._function = function
        self._scope = scope

        # Operation chaining
        self._prev = prev
        self._next = next

    @property
    def function(self) -> callable:
        return self._function
    
    @function.setter
    def function(self, function: callable) -> None:
        self._function = function
    
    @property
    def scope(self) -> Scope:
        return self._scope

    @property
    def prev(self) -> Operation:
        return self._prev

    @property
    def next(self) -> Operation:
        return self._next

    @prev.setter
    def prev(self, operation: Operation) -> None:
        self._prev = operation

    @next.setter
    def next(self, operation: Operation) -> None:
        self._next = operation
    
    @property
    def head(self) -> Operation:
        """
        Returns: the first operation of the chain.
        """
        if self.has_prev:
            return self._next.head
        return self
    
    @property
    def tail(self) -> Operation:
        """
        Returns: the last operation of the chain.
        """
        if self.has_next:
            return self._next.tail
        return self

    @property
    def has_prev(self) -> bool:
        return self._prev is not None

    @property
    def has_next(self) -> bool:
        return self._next is not None

    def before_put(self, operation: Operation) -> Operation:
        """
        Insert an operation in the chain, before the current one.
        Parameters:
            - operation : the operation to insert in the chain.
        Returns: the inserted operation
        """    
        self._prev.next = operation
        operation.last.next = self
        return operation

    def after_put(self, operation: Operation) -> Operation:
        """
        Insert an operation in the chain, after the current one.
        Parameters:
            - operation : the operation to insert in the chain.
        Returns: the inserted operation
        """   
        if self._next:
            operation.next = self._next
        self._next = operation
        operation.prev = self
        return operation

    def at_tail_put(self, operation: Operation) -> Operation:
        """
        Insert an operation at the very end of the chain.
        Parameters:
            - operation : the operation to insert in the chain.
        Returns: the inserted operation
        """
        return self.tail.after_put(operation)
        
    def execute(self) -> any:
        """
        Executes the operation.
        If there was any previous operation in the chain, inject the
        Returns: the result of the operation.
        """
        result = self.function(*self._scope.args, **self._scope.kwargs)
        if self._next:
            self._next._prev_result = result
        return result


def operation(**functions):
    """
    This decorator can take any number of arguments.
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

            scope = Scope(args=args, kwargs=kwargs)

            def apply(f, key):
                def arguments(*a, **kw):
                    res = f(*a, **kw)
                    scope.add_kw_arg(key, res)
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
                op = functions[key](*args, **kwargs) #1
                function = op.function               #2            
                op.function = apply(function, key)                
                chain.at_tail_put(op)

            chain.at_tail_put(Operation(continuation, scope=scope))

            return chain.next
        
        return wrapper
    return decorator

def loop(collection: list, function: callable) -> Operation:
    """
    Creates a sequence of function calls with, in argument the items of a collection.
    Parameters:
        - collection: the collection of items to iterate over.
        - function: the function to call with each item of the collection in argument, the function itself must return an Operation or use the @operation decorator.
    Returns: the first Operation of the chain of operations.
    """
    chain = Operation(lambda: ())
    
    if not collection:
        return chain
    
    for item in collection:
        chain.at_tail_put(function(item))

    return chain.next
