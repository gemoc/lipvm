from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer
from backend.interpreter import Interpreter

class LanguageExecutionServerProtocol:

    def __init__(self, interpreter: Interpreter, server: SimpleJSONRPCServer):
        self._interpreter = interpreter

        server.register_function(self.execute)

    def execute(self, code: str) -> None:
        self._interpreter.async_interpret(code)

class DebugAdapterProtocol:

    def __init__(self, interpreter: Interpreter, server: SimpleJSONRPCServer):
        self._interpreter = interpreter

        server.register_function(self.halt)
        server.register_function(self.proceed)
        server.register_function(self.step)

    def halt(self) -> None:
        self._interpreter.halt()

    def proceed(self) -> None:
        self._interpreter.async_proceed()

    def step(self) -> None:
        self._interpreter.async_step()