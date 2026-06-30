from core.operation import Operation, operation


def test_execute_uses_constructor_args():
    # Given
    result = []
    op = Operation(lambda a, b: result.append((a, b)), args=(1, 2))
    
    # When
    op.execute()

    # Then
    assert result == [(1, 2)]


def test_predecessor_result_is_captured_as_next_argument():
    # Given
    received = []
    consumer = Operation(lambda value: received.append(value), receives_result=True)
    producer = Operation(lambda: "result", continuation=consumer)

    # When
    producer.execute()
    consumer.execute()

    # Then
    assert consumer.args == ("result",)
    assert received == ["result"]


def test_result_not_forwarded_without_receives_result_flag():
    # Given
    consumer = Operation(lambda: None)  # receives_result defaults to False
    producer = Operation(lambda: "ignored", continuation=consumer)

    # When
    producer.execute()

    # Then
    assert consumer.args == ()


def test_operation_is_replayable_with_captured_args():
    # Given
    calls = []
    op = Operation(lambda x: calls.append(x), args=("captured",))

    # When
    op.execute()
    op.execute()  
    op.execute()

    # Then
    assert calls == ["captured", "captured", "captured"]


def test_decorator_returns_operation():
    # Given
    ran = []
    class Util:
        @operation
        def evaluate(self, runtime):
            ran.append((self, runtime))
            return "done"

    # When
    util = Util()
    op = util.evaluate("ctx")

    # Then
    assert isinstance(op, Operation)
    assert op.args == (util, "ctx")
    assert ran == []

    assert op.execute() == "done"
    assert ran == [(util, "ctx")]


def test_operation_is_replayable():
    # Given
    ran = []
    class Util:
        @operation
        def evaluate(self, runtime):
            ran.append(runtime)

    # When
    util = Util()
    op = util.evaluate("ctx")

    op.execute()
    op.execute()

    # Then
    assert ran == ["ctx", "ctx"]
