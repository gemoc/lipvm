import os
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")  # this module can get imported just for class discovery (see registry.py), not necessarily to actually render -- suppress pygame's own import-time banner so it doesn't pollute stdout for callers who never asked for it
import pygame
from abc import ABC, abstractmethod

from languages.sysmlv2.simulation_models.fischertechnik.enums import TokenColorKind


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
                       mouse_pos: tuple[int, int], machine, selected_color: TokenColorKind, on_select_color,
                       field_values: dict) -> list[tuple[pygame.Rect, object]]:
        """Optional per-machine button row drawn under this machine's panel
        lines (and any panel_input_fields() row) -- default: none. Only
        `TokenProducerVisualization` overrides this today (Emit
        Token/Random Emit, plus its own color picker drawn via
        `factory_visualization.draw_color_palette()` -- `selected_color`/
        `on_select_color` exist on this signature for exactly that,
        threaded down rather than drawn generically since no other
        machine kind needs them). A drawer without buttons -- or without
        a use for `selected_color`/`on_select_color`/`field_values` --
        just ignores whichever it doesn't need (this method's own default
        ignores every one of them). `selected_color` is rebuilt fresh
        every frame (same as `field_values`), so a closure reading it
        always sees whatever's currently picked at the moment it's
        actually clicked, not whatever it was when the button was drawn.
        """
        return []

    def panel_input_fields(self, screen: pygame.Surface, x: int, y: int, font: pygame.font.Font,
                            machine, field_values: dict, focused_field) -> list[tuple[str, pygame.Rect]]:
        """Optional per-machine text-input-field row, drawn under
        panel_lines() and above panel_buttons() -- default: none. Only
        `VacuumGripperVisualization` overrides this today (target/move-start
        horizontal+rot fields feeding goToPosition()/move()).

        `field_values` (dict[str, str], keyed by field name) and
        `focused_field` (the currently-focused field's key, or None) are
        both owned by `run()` (same pattern as `selected_color`/
        `on_select_color` for the token palette) -- this method only reads
        current text to render each box, and reports back (field_key,
        hit_rect) pairs so `run()`'s event loop can hit-test clicks-to-focus
        and route keystrokes to the right entry in `field_values`, without
        this drawer needing to know anything about keyboard handling
        itself.
        """
        return []
