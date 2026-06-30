from __future__ import annotations

from enum import Enum
from typing import Any

from pyecore.ecore import *

from core.edit import *
from core.language import Scenario, RuntimeState


class ProgramUpdateOption(Enum):

    RESTART = "RESTART"
    HOTSWAP = "HOTSWAP"


class VirtualMachine:
    """
    A virtual machine runs a single program: it evaluates the program's
    definitions followed by a scenario's commands, and exposes the
    resulting chain of operations so it can be stepped through, paused,
    resumed, or edited while running.
    """

    def __init__(self) -> None:
        self.scenario = None
        self.running = False

        self._operation = None
        self._runtime = None

        self._edit_script = None

    @property
    def state(self) -> RuntimeState:
        return self._runtime

    def init(self) -> None:
        self._runtime = RuntimeState()
        self._operation = self.scenario.init(self._runtime)

    def stop(self) -> None:
        self.running = False

    def step(self) -> Any:
        """Execute one visible step: advance through internal glue operations
        until reaching the next operation that corresponds to an AST node.
        """
        self._apply_pending_edits()

        result = None
        while self._operation is not None:
            result = self._operation.execute()
            self._operation = self._operation.continuation
            if self._operation is None or self._operation.has_syntax:
                break

        return result

    def run(self) -> Any:
        """Run the program to completion, stepping through AST nodes one by one."""
        if not self._operation:
            raise RuntimeError("Virtual machine not initialized, please call init() first.")

        result = None
        self.running = True
        while self.running and self._operation is not None:
            result = self.step()

        return result

    def udpate(self, edit_script: EditScript, option: ProgramUpdateOption) -> None:
        """Apply a set of edits to the running program.

        With RESTART, the edits are applied immediately and execution restarts
        from scratch with the updated syntax tree.

        With HOTSWAP, execution keeps running and the edits are held until the
        VM reaches a safepoint, at which point they are applied in place.
        """
        self.stop()

        self._edit_script = edit_script
        self._edit_script.attach_to(self.scenario)

        if option == ProgramUpdateOption.RESTART:
            self._edit_script.apply()
            self.init()
            self._edit_script.migrate(self._runtime)
            self._edit_script = None
        else:
            self._edit_script.prepare(self._runtime)

        self.run()

    def _apply_pending_edits(self) -> None:
        """If a safepoint has been reached, apply the pending edits and migrate the runtime."""
        if not self._edit_script:
            return None

        syntax = self._operation.syntax_element
        if syntax is None or not syntax.isSafeToMigrate(self._runtime):
            return None

        self._edit_script.apply()
        self._edit_script.migrate(self._runtime)
        self._edit_script = None
