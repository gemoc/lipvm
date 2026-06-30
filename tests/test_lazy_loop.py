from core.operation import Operation, lazy_loop


# --- Helpers ---

def _run(op: Operation) -> None:
    current = op
    while current:
        current.execute()
        current = current.continuation if current.has_continuation else None


# --- Tests ---

def test_empty_collection_returns_none():
    # Given
    collection = []
    iteration = lambda item: Operation(lambda: None)
    
    # When
    result = lazy_loop(collection, iteration)

    # Then
    assert result is None


def test_executes_all_items_in_order():
    # Given
    results = []

    # When
    chain = lazy_loop([1, 2, 3], lambda x: Operation(lambda val=x: results.append(val)))
    _run(chain)

    # Then
    assert results == [1, 2, 3]


def test_return_loop_with_iteration_built_lazily():
    # Given
    elements = []

    def tracked(x):
        elements.append(x)
        return Operation(lambda: None)

    # When: chain is built but not yet executed
    chain = lazy_loop([1, 2, 3], tracked)

    # Then: only the first element is materialized
    assert elements == []

    # When: chain runs to completion
    _run(chain)

    # Then: all elements were materialized
    assert elements == [1, 2, 3]


def test_repeats_while_true_stops_when_false():
    # Given
    results = []
    iterations = [0]

    def check():
        iterations[0] += 1
        return iterations[0] <= 2  # True on checks 1 and 2, False on check 3

    # When
    chain = lazy_loop([10, 20], lambda x: Operation(lambda val=x: results.append(val)), Operation(check))
    _run(chain)

    # Then: collection ran twice
    assert results == [10, 20, 10, 20]


def test_with_condition_false_on_first_check_never_executes_body():
    # Given
    results = []

    # When
    chain = lazy_loop([1, 2], lambda x: Operation(lambda val=x: results.append(val)), Operation(lambda: False))
    _run(chain)

    # Then
    assert results == []


def test_with_condition_elements_built_lazily_per_iteration():
    # Given
    elements = []

    def tracked(x):
        elements.append(x)
        return Operation(lambda: None)

    iterations = [0]

    def check():
        iterations[0] += 1
        return iterations[0] == 1  # True once, then False

    # When: chain is built but not yet executed
    chain = lazy_loop([1, 2], tracked, Operation(check))

    # Then: nothing called yet
    assert elements == []

    # When: chain runs to completion
    _run(chain)

    # Then: body elements built exactly once during the single iteration
    assert elements == [1, 2]
