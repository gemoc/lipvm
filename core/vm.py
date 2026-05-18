from pyecore import behavior

from core.operations import Operation
from core.metametamodel import *

"""
Must stay a constant/singleton
"""
VM = VirtualMachine()

@VirtualMachine.behavior
@property
def operation(self):
    return self._operation

def store_operation(self):
    self._operation

@VirtualMachine.behavior
def start(self, model, runtime):
    self._operation = model.evaluate(runtime)
    self.running = True
    return self.run()

@VirtualMachine.behavior
def run(self):
    result = self._operation.execute()
    while self._operation.has_next and self.running:
        self._operation = self._operation.next
        result = self._operation.execute()
    return result

@VirtualMachine.behavior
def pause(self):
    self.running = False

@VirtualMachine.behavior
def restart(self):
    self.running = True
    return self.run()


def inject_getattr():
    """
    Function needed to avoid having __getattr__ defined in the scope of the file.
    When invoked in the scope of the file it overrides the default python behavior on import.
    The expected __getattr__ in the scope of a file expect only one argument, the name,
    whereas we want to inject our __getattr__ method in the class of an object, so we take one
    extra argument, self, the reference to the instance.  
    """
    @RuntimeState.behavior
    def __getattr__(self, attr_name: str):
        for element in self.elements:
            if element.name == attr_name:
                return element
        raise Exception(attr_name + " not found in RuntimeState")

inject_getattr()