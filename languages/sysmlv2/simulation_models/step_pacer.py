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

    @property
    def period(self) -> int:
        return self._period

    @period.setter
    def period(self, value: int) -> None:
        """Changeable live (e.g. a speed slider) -- takes effect on each
        key's next `is_due()` call. Doesn't touch `_counters`: a key
        already partway toward the old period just measures the rest of
        its wait against the new one, which can make its very next call
        due a little earlier or later than a full fresh period would --
        acceptable one-off jitter for a live speed change, not worth
        resetting every in-flight counter over.
        """
        self._period = value

    def is_due(self, key) -> bool:
        elapsed = self._counters.get(key, 0) + 1
        if elapsed < self._period:
            self._counters[key] = elapsed
            return False
        self._counters[key] = 0
        return True

    def reset(self, key):
        self._counters.pop(key, None)
