class StepPacer:
    """Throttles per-key calls so the caller only gets a "yes, act now"
    once every `period` calls for that key -- decouples "how often this
    can be checked" (e.g. every rendered frame) from "how often it should
    actually do something" (e.g. once every 0.5s). Framework-agnostic:
    counts plain calls, knows nothing about real time.
    """

    def __init__(self, period: int):
        self._period = period
        self._counters = {}

    def is_due(self, key) -> bool:
        elapsed = self._counters.get(key, 0) + 1
        if elapsed < self._period:
            self._counters[key] = elapsed
            return False
        self._counters[key] = 0
        return True

    def reset(self, key):
        self._counters.pop(key, None)
