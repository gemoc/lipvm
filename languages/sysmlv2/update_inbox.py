"""The folder update scripts are dropped into during a live demo (the "update
button", TODOLIST-NOW.md).

An update file is a Python file defining `UPDATES`, a non-empty list of
updates (e.g. `ChangeRuntimeAttributeValue`s). The visualization's button is
enabled when the folder holds exactly one such file; clicking it loads the
file into one `AtomicUpdate` and, once submitted, the file is moved to the
`applied/` subfolder, so it can't be submitted twice and a record of what ran
remains.

This module only knows the folder and the files: listing, loading, moving.
When to look, and handing the update to the interpreter, is the driver's job.
"""
import importlib.util
import os
import shutil
import time
from dataclasses import dataclass
from typing import Optional

from languages.sysmlv2.updates import AtomicUpdate

APPLIED_FOLDER = "applied"
UPDATES_NAME = "UPDATES"


class UpdateFileError(Exception):
    """An update file that can't be loaded; the message says why."""


@dataclass(frozen=True)
class InboxState:
    """What the folder holds right now: `file` is the one update file ready to
    submit, or None; `message` explains why not (None when ready or empty).
    """
    file: Optional[str]
    message: Optional[str] = None

    @property
    def ready(self) -> bool:
        return self.file is not None


class UpdateInbox:
    """The folder update files are dropped into. Assumes one file at a time:
    more than one is reported, not guessed between.

    Ignores files whose name starts with "_" or "." (e.g. `__init__.py`,
    editor temporary files) and anything in subfolders, including `applied/`.
    """

    def __init__(self, folder: str):
        self.folder = folder
        self.applied_folder = os.path.join(folder, APPLIED_FOLDER)
        os.makedirs(self.applied_folder, exist_ok=True)

    def files(self) -> list[str]:
        """The update files in the folder, sorted by name."""
        return sorted(
            os.path.join(self.folder, name) for name in os.listdir(self.folder)
            if name.endswith(".py") and not name.startswith(("_", "."))
            and os.path.isfile(os.path.join(self.folder, name)))

    def state(self) -> InboxState:
        """Cheap (a directory listing), meant to be asked every half second
        or so."""
        files = self.files()
        if len(files) == 1:
            return InboxState(file=files[0])
        if not files:
            return InboxState(file=None)
        names = ", ".join(os.path.basename(path) for path in files)
        return InboxState(file=None, message=f"More than one update file, expected one: {names}")

    def load(self, path: str) -> AtomicUpdate:
        """Runs the file and returns its `UPDATES` as one AtomicUpdate.
        Raises UpdateFileError if the file fails to run, has no `UPDATES`,
        or `UPDATES` isn't a non-empty list AtomicUpdate accepts.
        """
        name = os.path.basename(path)
        spec = importlib.util.spec_from_file_location(f"lipvm_update_file_{time.time_ns()}", path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as error:  # the file is user code: any error in it is a load failure
            raise UpdateFileError(f"{name}: {type(error).__name__}: {error}") from error

        updates = getattr(module, UPDATES_NAME, None)
        if updates is None:
            raise UpdateFileError(f"{name}: defines no {UPDATES_NAME} list")
        if not isinstance(updates, (list, tuple)):
            raise UpdateFileError(f"{name}: {UPDATES_NAME} must be a list, got {type(updates).__name__}")
        try:
            return AtomicUpdate(updates)
        except ValueError as error:
            raise UpdateFileError(f"{name}: {error}") from error

    def mark_applied(self, path: str) -> str:
        """Moves the file into `applied/` (adding a timestamp to the name if a
        file of that name was applied before) and returns its new path.
        """
        stem, extension = os.path.splitext(os.path.basename(path))
        target = os.path.join(self.applied_folder, stem + extension)
        if os.path.exists(target):
            target = os.path.join(self.applied_folder, f"{stem}_{time.strftime('%Y%m%d-%H%M%S')}{extension}")
        shutil.move(path, target)
        return target
