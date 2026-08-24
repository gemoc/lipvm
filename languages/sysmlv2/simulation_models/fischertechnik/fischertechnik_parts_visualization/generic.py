import os
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")  # this module can get imported just for class discovery (see registry.py), not necessarily to actually render -- suppress pygame's own import-time banner so it doesn't pollute stdout for callers who never asked for it
import pygame
from abc import ABC, abstractmethod


class MachineVisualization(ABC):
    """Shared base for one machine kind's own drawer -- one subclass per
    `PartSimulationModel` subclass that wants to appear in the viewport
    (`ConveyorBeltMachine`, and any future machine kind, e.g.
    `VacuumGripperMachine`). Lives in this Fischertechnik-specific package
    (not `languages/sysmlv2/simulation_models/generic.py`) since
    `draw(self, screen, machine)` is a pygame-shaped contract -- pygame is
    Fischertechnik's own rendering choice, not something a future
    non-pygame domain's visualization would share, same reasoning
    `SimulationVisualization`'s own docstring already gives for staying
    implementation-free. Keeps pygame-specific code out of the machine
    classes themselves -- `Factory`/`ConveyorBeltMachine`/
    `VacuumGripperMachine` stay renderer-free -- while letting
    `factory_visualization.py`'s viewport dispatch generically via
    `scan_for_subclasses()` (`registry.py`) instead of hardcoding a call
    per machine type.
    """

    machine_type: type = None  # subclass sets this to the PartSimulationModel subclass it draws
    panel_label: str = None    # subclass sets this to the side panel's per-kind heading prefix, e.g. "Belt"

    @abstractmethod
    def draw(self, screen: pygame.Surface, machine) -> None:
        raise NotImplementedError("Sub-class must implement this method.")

    @abstractmethod
    def panel_lines(self, machine) -> list[str]:
        """Live attribute text lines shown under this machine's side-panel
        block (`FischertechnikVisualization._draw_machine_panel`) -- e.g.
        `["conveyorSensFeed: True", ...]`. Mandatory: every machine kind
        should show *something* live, even if just `currentCommand`.
        """
        raise NotImplementedError("Sub-class must implement this method.")

    def panel_buttons(self, screen: pygame.Surface, x: int, y: int, font: pygame.font.Font,
                       mouse_pos: tuple[int, int], machine, on_place_token) -> list[tuple[pygame.Rect, object]]:
        """Optional per-machine button row drawn under this machine's panel
        lines -- default: none. Only `ConveyorBeltVisualization` overrides
        this today (token-placement buttons); a machine kind with no
        manual control to offer (e.g. VacuumGripperMachine, for now) just
        keeps this default.
        """
        return []
