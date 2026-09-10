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

        self._pending_update = None

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

        A pending update is taken into account at each node boundary, honoring
        its checkpoint's timing: a before-point update is applied just before
        the node's operation executes, an after-point update just after.
        """
        result = None
        while self._operation is not None:
            self._apply_pending_update(before=True)
            result = self._operation.execute()
            self._apply_pending_update(before=False)
            self._operation = self._operation.continuation
            if self._operation is not None and self._operation.is_step:
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

    def update(self, update: Update, option: ProgramUpdateOption) -> None:
        """Take a code change (an Update) into account.

        With RESTART, the update is applied immediately and execution restarts
        from scratch on the changed syntax tree.

        With HOTSWAP, execution keeps running and the update is held pending
        until the VM reaches a checkpoint of the update's checkpoint_type()
        whose condition() holds, at which point it is applied in place (see
        _apply_pending_update).
        """
        self.stop()

        if update.edit_script is not None:
            update.edit_script.attach_to(self.scenario)

        if option == ProgramUpdateOption.RESTART:
            if update.edit_script is not None:
                update.edit_script.apply()
            self.init()
            update.apply(self._runtime)
        else:
            self._pending_update = update

        self.run()

    def _apply_pending_update(self, before: bool) -> None:
        """If a pending update's checkpoint has been reached and its condition
        holds, apply its edit script and run its migration.

        Called twice around each operation's execution -- with before=True
        just before it runs, and before=False just after. The current
        operation's syntax node must (1) be an update point, (2) be an instance
        of the update's declared checkpoint_type(), and (3) have the timing
        that matches this call (a before-point on the before=True call, an
        after-point on the before=False call). Only then is the update's
        condition() checked and, if true, the change applied: the edit script
        edits the syntax, then apply() migrates the live runtime to match.
        """
        update = self._pending_update
        if update is None:
            return None

        node = self._operation.syntax_element if self._operation is not None else None
        if node is None:
            return None

        if not node.isUpdatePoint() or not isinstance(node, update.checkpoint_type()):
            return None

        # Honor the checkpoint's before/after timing: only take the update
        # into account on the call whose timing the node's type calls for.
        if node.isUpdateBefore() != before:
            return None

        if not update.condition(self._runtime):
            return None

        if update.edit_script is not None:
            update.edit_script.apply()
        update.apply(self._runtime)
        self._pending_update = None
