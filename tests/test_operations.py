from core.operations import *


def collect_chain(head):
    """Helper function: executes every operation of a chain, in order, and return the list of results."""
    results = []
    current = head
    while True:
        results.append(current.execute())
        if not current.has_next:
            break
        current = current.next
    return results


def test_operation_chaining_with_after_put():

    # Given: three operations chained with after_put.
    op1 = Operation(lambda: "a")
    op2 = Operation(lambda: "b")
    op3 = Operation(lambda: "c")

    op1.after_put(op2)
    op2.after_put(op3)

    # Then: the head of the chain reports itself as its own head...
    assert op1.head is op1

    assert op1.tail is op3
    assert op2.tail is op3
    assert op3.tail is op3

    assert op1.has_prev is False
    assert op1.has_next is True
    assert op3.has_next is False

    assert collect_chain(op1) == ["a", "b", "c"]


def test_operation_before_put_inserts_in_chain():

    # Given: a two-operation chain.
    op1 = Operation(lambda: "first")
    op3 = Operation(lambda: "last")
    op1.after_put(op3)

    # When: a new operation is inserted before op3.
    op2 = Operation(lambda: "middle")
    op3.before_put(op2)

    # Then: the chain order becomes op1 -> op2 -> op3.
    assert collect_chain(op1.head) == ["first", "middle", "last"]


def test_operation_execute_propagates_prev_result():

    # Given: a chain of two operations.
    op1 = Operation(lambda: 10)
    op2 = Operation(lambda: 20)
    op1.after_put(op2)

    # Initially there is no previous result for op2.
    assert op2.prev_result is None

    # When: the first operation is executed.
    op1.execute()

    # Then: its result is injected into the next operation's scope.
    assert op2.prev_result == 10


def test_operation_clone_creates_unlinked_operation():

    # Given: an operation with arguments, chained after another operation.
    op1 = Operation(lambda: None)
    op2 = Operation(lambda x: x * 2, arguments=OperationArguments(args=[5]))
    op1.after_put(op2)

    # When: the operation is cloned.
    clone = op2.clone()

    # Then: the clone is a distinct object that executes the same function...
    assert clone is not op2
    assert clone.function is op2.function
    assert clone.execute() == 10

    # ...and is unlinked from the chain it was cloned from.
    assert clone.has_prev is False
    assert clone.has_next is False


def test_loop_with_empty_collection_returns_noop_operation():

    # Given/When: a loop is built over an empty collection.
    chain = loop([], lambda item: Operation(lambda: item))

    # Then: it returns a single no-op operation that does nothing.
    assert chain.execute() == ()
    assert chain.has_next is False


def test_loop_without_condition_executes_each_item_in_order():

    # Given: a collection of items and a function building an operation per item.
    log = []

    def make_operation(item):
        return Operation(lambda i=item: log.append(i))

    # When: a loop is built over the collection and fully executed.
    chain = loop([1, 2, 3], make_operation)
    collect_chain(chain)

    # Then: each item has been processed exactly once, in order.
    assert log == [1, 2, 3]


def test_loop_with_condition_repeats_while_true():

    # Given: a body operation that increments a counter, and a condition that
    # stays True (i.e. keeps repeating the loop body) while the counter is
    # below a threshold.
    state = {"count": 0}
    log = []

    def make_operation(item):
        def execute(i=item):
            state["count"] += 1
            log.append(i)
        return Operation(execute)

    condition = Operation(lambda: state["count"] < 3)

    # When: a conditional loop is built and fully executed.
    chain = loop(["step"], make_operation, condition)
    collect_chain(chain)

    # Then: the body has been executed repeatedly until the condition became False.
    assert log == ["step", "step", "step"]
    assert state["count"] == 3


def test_operation_decorator_without_extra_arguments():

    # Given: a class whose evaluate method is decorated with @operation().
    class Node:
        @operation()
        def evaluate(self, value):
            return f"evaluated:{value}"

    # When: evaluate is called.
    node = Node()
    op = node.evaluate("input")

    # Then: it returns the evaluated input
    assert op.execute() == "evaluated:input"


def test_operation_decorator_injects_named_operation_results():

    # Given: a class whose evaluate method depends on the result of another
    # operation, injected via the @operation decorator's keyword arguments
    # (similar to how IfDoElse depends on its condition's result).
    class Node:
        @operation(extra=lambda node, value: Operation(lambda: value * 2))
        def evaluate(self, value, extra=None):
            return f"value={value}, extra={extra}"

    # When: evaluate is called and the resulting chain is fully executed.
    node = Node()
    op = node.evaluate(5)

    results = collect_chain(op)

    # And: the final result has access to the "extra" value computed earlier.
    assert results[-1] == "value=5, extra=10"
