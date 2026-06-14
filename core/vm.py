from __future__ import annotations

from typing import Any, LiteralString, List

from pyecore.ecore import *

from core.edit import *
from core.language import AbstractSyntaxElement, RuntimeState

class ProgramUpdateOption:

    RESTART = None
    HOTSWAP = None

    def __init__(cls):
        super().__init__()
        cls.RESTART = cls("RESTART")
        cls.HOTSWAP = cls("HOTSWAP")

class VirtualMachine:
    """
    A virtual machine runs a single program: it evaluates the program's
    definitions followed by a scenario's commands, and exposes the
    resulting chain of operations so it can be stepped through, paused,
    resumed, or edited while running.
    """

    def __init__(self) -> None:
        self._scenario_syntax = None
        self._program_syntax = None

        self._operation = None
        self._runtime = None

    @property
    def scenario_syntax(self) -> AbstractSyntaxElement:
        return self._scenario_syntax

    @scenario_syntax.setter
    def scenario_syntax(self, scenario_syntax: AbstractSyntaxElement) -> None:
        """
        Sets the expression used to start the execution.
        """
        self._scenario_syntax = scenario_syntax

    @property
    def program_syntax(self) -> AbstractSyntaxElement:
        return self._program_syntax

    @program_syntax.setter
    def program_syntax(self, program_syntax: AbstractSyntaxElement) -> None:
        """
        Sets the program's definitions, evaluated before the scenario.
        """
        self._program_syntax = program_syntax

    @property
    def state(self) -> RuntimeState:
        if not self._operation:
            raise Exception("Trying to access the state of a virtual machine that has not been executed yet.")
        return self._runtime

    def init(self) -> None:
        runtime = RuntimeState()
        self._runtime = runtime

        # First evaluate the program to read function definitions
        self._operation = self.program_syntax.evaluate(runtime)

        # Attach at the end of the program evaluation the operation that executes the scenario
        self._operation.tail.after_put(self.scenario_syntax.evaluate(runtime))

    def stop(self) -> None:
        self.running = False

    def step(self) -> Any:
        result = self._operation.execute()
        if self._operation.has_next:
           self._operation = self._operation.next
        return result

    def run(self) -> Any:
        if not self._operation:
            raise RuntimeError("Virtual machine not initialized, please call init() first.")

        self.running = True
        result = self._operation.execute()
        while self._operation.has_next and self.running:
            self._operation = self._operation.next
            result = self._operation.execute()
        return result

    def udpate(self, edit_script: EditScript, option: ProgramUpdateOption) -> None:
        """
        Update the definition of the program being executed.

        Parameters:
            - edit_script: the edit operations to apply to the running syntax trees.
            - option: whether to RESTART the execution from scratch or HOTSWAP it in place.
        """

        self.stop()

        edit_script.attach_to(self.scenario_syntax)
        edit_script.attach_to(self.program_syntax)

        if option == ProgramUpdateOption.RESTART:
            self.scenario_syntax = self.scenario_syntax.apply_edit_operations()
            self.program_syntax = self.program_syntax.apply_edit_operations()
            self.init()

        self.run()
