"""Updates derived from the minilogo language.

An Update is a code change a language engineer makes available to be folded
into a running program at a checkpoint (see core.edit.Update and the
UpdatePoint hierarchy in core.language). MiniLogo marks every Command as a
"before" checkpoint (see Command in syntax.py), because a program is a flat
sequence of commands run one at a time by lazy_loop, which re-reads the
command list by index -- so an edit to a not-yet-reached command is picked up
naturally, and a command boundary is a consistent point to apply one.

The updates below are the meaningful changes that fall out of the language's
own constructs:

  * InsertMove / RemoveCommand -- restructure the remaining drawing plan.
    Only safe while the pen is up: with the pen down a line is mid-draw, and
    re-planning the upcoming moves could split it. Hence PenUpUpdate.
  * RecolorFromNow -- change a Color command and migrate the live pen so the
    new color takes effect immediately, not only when that command is next
    reached. Always safe, and shows migration reconciling runtime with syntax.

Each update owns its edit script: it is built from the target node identifiers
in the constructor, not supplied by the caller.
"""

from pyecore.ecore import *

from core.edit import (
    EditScript,
    InsertSyntaxOperation,
    UpdateSyntaxOperation,
    DeleteSyntaxOperation,
    Update,
)
from core.language import RuntimeState

from languages.minilogo.runtime import PenStatus, ColorCode
from languages.minilogo.syntax import Command, Move, Literal


class MiniLogoUpdate(Update):
    """Base for minilogo updates. Every Command is a before-checkpoint, so by
    default an update is considered at any command boundary; override
    checkpoint_type() to restrict it to one kind of command."""

    def checkpoint_type(self) -> type:
        return Command


class PenUpUpdate(MiniLogoUpdate):
    """A minilogo update that is only safe to apply while the pen is up -- so
    restructuring the remaining drawing commands cannot split a line that is
    currently being drawn."""

    def condition(self, runtime: RuntimeState) -> bool:
        return runtime.penstate.status == PenStatus.up


class InsertMove(PenUpUpdate):
    """Insert a `Move x y` into the program at `index`, folded in at the next
    command boundary while the pen is up."""

    def __init__(self, program_identifier: int, index: int, x: int, y: int,
                 move_identifier: int = None, **kwargs) -> None:
        super().__init__(**kwargs)
        move = Move(x=Literal(value=x), y=Literal(value=y))
        if move_identifier is not None:
            move.identifier = move_identifier
        self.edit_script = EditScript(operations=[
            InsertSyntaxOperation(identifier=program_identifier, index=index, element=move)
        ])


class RemoveCommand(PenUpUpdate):
    """Delete the command at `index` from the program, while the pen is up."""

    def __init__(self, program_identifier: int, index: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.edit_script = EditScript(operations=[
            DeleteSyntaxOperation(identifier=program_identifier, index=index)
        ])


class RecolorFromNow(MiniLogoUpdate):
    """Change the color set by the `Color` command identified by
    `color_identifier`, and migrate the live pen so the new color takes effect
    immediately rather than only when that command is next reached."""

    def __init__(self, color_identifier: int, r: int, g: int, b: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self._color = (r, g, b)
        self.edit_script = EditScript(operations=[
            UpdateSyntaxOperation(
                identifier=color_identifier,
                attribute_name="colorCode",
                element=ColorCode(r=r, g=g, b=b),
            )
        ])

    def apply(self, runtime: RuntimeState) -> None:
        r, g, b = self._color
        runtime.penstate.color = ColorCode(r=r, g=g, b=b)
