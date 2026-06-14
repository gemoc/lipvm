from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer

from core.language import AbstractSyntaxElement
from core.edit import EditScript
from core.vm import VirtualMachine, ProgramUpdateOption

VM = VirtualMachine()

def start(program_syntax: AbstractSyntaxElement, scenario_syntax: AbstractSyntaxElement) -> None:

    VM.program_syntax = program_syntax
    VM.scenario_syntax = scenario_syntax

    VM.init()
    VM.run()  

def stop() -> None:
    
    VM.stop()

def update(edit_script: EditScript) -> None:
    
    VM.update(edit_script, ProgramUpdateOption.RESTART)
    


def listen(port: int = 8080):

    server = SimpleJSONRPCServer(('localhost', port))
    
    server.register_function(start)
    server.register_function(stop)
    server.register_function(update)

    print(f"LipVM LESP listening at localhost:{port}")
    server.serve_forever()
