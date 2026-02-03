from sys import argv
from importlib import import_module

from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer

from backend.parser import Parser
from backend.interpreter import Interpreter
from backend.protocols import DebugAdapterProtocol, LanguageExecutionServerProtocol

class LipVM:

    def __init__(self, module: str):
        # Import language visitor from module
        LanguageVisitor = getattr(import_module(module + ".LanguageVisitorImpl"), 'LanguageVisitorImpl')

        # Create the parser and interpreter
        parser = Parser(module)
        self._interpreter = Interpreter(parser, LanguageVisitor)

    def serve(self, port: int) -> None:
        server = SimpleJSONRPCServer(('localhost', port))

        DebugAdapterProtocol(self._interpreter, server)
        LanguageExecutionServerProtocol(self._interpreter, server)

        server.serve_forever()

    @property
    def interpreter(self) -> Interpreter:
        return self._interpreter