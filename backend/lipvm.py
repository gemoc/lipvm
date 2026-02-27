from importlib import import_module

from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer

from backend.parser import Parser
from backend.interpreter import Interpreter
from backend.protocols import DebugAdapterProtocol, LanguageExecutionServerProtocol

class LipVM:

    def __init__(self, module: str):
        # Import language visitor from module
        interpreter = getattr(import_module(module + ".LanguageInterpreter"), 'LanguageInterpreter')

        # Create the parser and interpreter
        parser = Parser(module)
        self._interpreter = interpreter(parser)

    def serve(self, port: int) -> None:
        server = SimpleJSONRPCServer(('localhost', port))

        DebugAdapterProtocol(self._interpreter, server)
        LanguageExecutionServerProtocol(self._interpreter, server)

        server.serve_forever()

    @property
    def interpreter(self) -> Interpreter:
        return self._interpreter