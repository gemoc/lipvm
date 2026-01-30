from backend.Stack import Stack

class Environment:

    def __init__(self):

        self._ip = 0
        self._stack = Stack()
        self._globals = {}
        self._heap = {}
        self._current_line = 0  # Track current source line number

    @property
    def ip(self):
        return self._ip

    @ip.setter
    def ip(self, ip):
        self._ip = ip

    @property
    def stack(self):
        return self._stack
    
    @property
    def globals(self):
        return self._globals

    @property
    def heap(self):

        return self._heap

    @property
    def current_line(self):
        return self._current_line

    @current_line.setter
    def current_line(self, line):
        self._current_line = line

    def remove_key_from_heap(self, key: str):

        # Find the environment that owns it
        if not self.is_key_exist_in_heap(key):

            raise KeyError(key, " does not exist in current environment")

        self._heap.pop(key)

    def is_key_exist_in_heap(self, key: str):

        return key in self._heap

    def store_value_in_heap(self, key: str, value):

        self._heap[key] = value

    def get_value_from_heap(self, key: str):

        # Find the environment that owns it
        if self.is_key_exist_in_heap(key):

            return self._heap[key]

        raise KeyError(key, " does not exist in current environment")
