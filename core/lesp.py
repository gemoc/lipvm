from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer

from core.vm import VM 


class Mock:

    def __init__(self, expression: str, mock: str):
        self._expression = expression
        self._mock = mock

    @property
    def expression(self):
        return self._expression
    
    @property
    def mock(self):
        return self._mock

class Example:

    def __init__(self, source: str, mocks: list[Mock] = []):
        self._source = source
        self._mocks = mocks

    @property
    def source(self):
        return self._source

    @property
    def mocks(self):
        return self._mocks

contexts = {}

def start(context_identifier: str = None, example: Example = None) -> None:
    VM.pause()

def pause() -> None:
    VM.pause()

def current_context_identifier() -> str:
    identifier = hash(VM.operation)
    contexts[identifier] = VM.operation
    return identifier


def start(port: int = 8080):

    server = SimpleJSONRPCServer(('localhost', port))
    
    server.register_function(start)
    server.register_function(pause)
    server.register_function(current_context_identifier)