"""Interpreter-side synchronization of live updates with the simulation:
the `SynchronizationManager`, which records what live updates change in the
running model and sends it to the simulation, and the commands it sends.
Generic (domain- and language-agnostic), like facade_proxy.py, whose channel
and bridge it uses; split out of facade_proxy.py, which stays the plain
thread-confinement infrastructure.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.language import RuntimeStateElement
from languages.sysmlv2.simulation_models.facade_proxy import SimulationBridge, ThreadChannel
from languages.sysmlv2.simulation_models.generic import BaseSimulationModel


class ModelUpdateCommand(ABC):
    """One change a live update made to the running model, sent by the SysML
    interpreter to the simulation -- fire-and-forget. One subclass per kind
    of change.

    Visitor-style: the simulation side calls `accept(model)` on each command,
    and each kind calls its own operation of the simulation interface
    (`BaseSimulationModel`, the visitor), whose implementation (e.g.
    `Factory`) does the actual work. So the simulation side never checks a
    command's type; a new kind of change is a new subclass here plus, if it
    needs one, a new abstract operation on `BaseSimulationModel`, which every
    simulation must then implement.

    The commands of one live update travel together: `SynchronizationManager.
    flush` puts them on `model_update_queue` as **one** item (a list), so the
    simulation applies every change of the update in the same frame.
    """

    @abstractmethod
    def accept(self, model: BaseSimulationModel) -> None:
        """Applies this change to `model` (simulation thread)."""
        raise NotImplementedError("Sub-class must implement this method.")


@dataclass(frozen=True)
class AddPartCommand(ModelUpdateCommand):
    """A live update added a part: the simulation creates its machine.

    qualified_name: the part's full SysML name
    part_def_name: which PartDef to construct
    attrs: attr_name -> (custom_class_name, values), the part's configured
        values (same shape as the startup path's InstantiateCommand.attrs)
    """
    qualified_name: str
    part_def_name: str
    attrs: dict

    def accept(self, model: BaseSimulationModel) -> None:
        model.instantiate_part(self.qualified_name, self.part_def_name, self.attrs)


@dataclass(frozen=True)
class SetAttributeCommand(ModelUpdateCommand):
    """A live update changed configured values of a running part: the
    simulation gives its machine the new values.

    qualified_name: the part's full SysML name
    attrs: attr_name -> (custom_class_name, values), only the changed
        attributes (e.g. {"placementCoordinate": ("FactoryCoordinate",
        {"x": 25.0, "y": 30.0, "degrees": 180.0})})
    """
    qualified_name: str
    attrs: dict

    def accept(self, model: BaseSimulationModel) -> None:
        model.set_attribute(self.qualified_name, self.attrs)


class SynchronizationManager(RuntimeStateElement):
    """Interpreter-side record of what live updates changed in the running
    model -- parts added and configured attribute values changed -- sent to
    the simulation as one batch per `flush` (design doc,
    Language-Safe-and-Execution-Tranquility-points.md, Topic 10 "Syncing a
    runtime change to the simulation"). Every live change reaches the
    simulation through here; only the startup parts take their own path
    (`PartInstantiation.evaluate`, `instantiate_queue`).

    A `RuntimeStateElement` reached as `runtime.synchronization_manager`,
    registered next to the channel. Unlike `ThreadChannel`, it is used by the
    interpreter thread only: the simulation thread never touches it.

    The record is filled by language-specific observers, which convert each
    change before calling `record`/`record_instantiation` (the same split as
    instantiation: the language converts, the bridge only enqueues). Updates
    always replace a configured value rather than change it in place, so a
    value converted when recorded is still the current one at `flush`.

    It also runs the interpreter's side of lockstep (design doc, Topic 10,
    "Lockstep while an update is pending") in `start_round`, and notes how
    the round's values were copied.

    self._additions: one `AddPartCommand` per part added since the last
        flush, in the order they were added
    self._record: qualified_name -> {attr_name: (custom_class_name, values)},
        the attribute changes since the last flush; the last change to an
        attribute wins. Turned into one `SetAttributeCommand` per part at
        `flush`
    self.values_copied_while_paused: whether this round waited for the
        simulation's question before its values were copied, i.e. copied while
        the simulation was paused; always False with lockstep disabled. Read by
        `TranquilUpdate.condition()` when lockstep is enabled
    self._owed_answer: the frame number of the question this round took,
        answered with "go" at the start of the next round; None if none
    self._last_answered: the last frame number answered, to check that each
        question is for a newer frame
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._additions = []
        self._record = {}
        self.values_copied_while_paused = False
        self._owed_answer = None
        self._last_answered = None

    @property
    def simulation_waiting(self) -> bool:
        """Whether the simulation is blocked waiting for this manager's "go"
        (a question was taken and not yet answered; it is answered at the
        next round start). The driver doesn't pause between steps meanwhile,
        so the answer isn't delayed, e.g. for the rest of the round in which
        an update was applied."""
        return self._owed_answer is not None

    def record(self, qualified_name: str, attr_name: str, value: tuple) -> None:
        """Remember that `attr_name` of part `qualified_name` now holds
        `value`, a `(custom_class_name, values)` pair."""
        self._record.setdefault(qualified_name, {})[attr_name] = value

    def record_instantiation(self, qualified_name: str, part_def_name: str, attrs: dict) -> None:
        """Remember that part `qualified_name` was added: the simulation must
        create a `part_def_name` machine with the configured values `attrs`
        (`{attr_name: (custom_class_name, values)}`)."""
        self._additions.append(AddPartCommand(qualified_name, part_def_name, attrs))

    def flush(self, channel: ThreadChannel) -> None:
        """Sends everything recorded since the last flush as one batch, a
        list of `ModelUpdateCommand`s: the added parts first (a part added now
        exists for what follows), then one `SetAttributeCommand` per changed
        part. Then starts a new record. Sends nothing when nothing was
        recorded, so a batch on the queue always means changes to apply.
        """
        commands = self._additions + [
            SetAttributeCommand(qualified_name, attrs) for qualified_name, attrs in self._record.items()
        ]
        if not commands:
            return
        SimulationBridge.send_model_update(channel, commands)
        self._additions = []
        self._record = {}

    def start_round(self, channel: ThreadChannel, update_pending: bool) -> None:
        """Called at the start of every round, before the events are drained
        and the values copied.

        First sends the previous round's batch, then "go" for the question
        that round took, in that order, so the simulation drains the batch
        before its next tick. Then, with lockstep enabled and an update
        pending, waits for the simulation's question: it has published and is
        blocked, so this round's values are copied while it is paused. Notes
        whether it waited; with lockstep disabled (nobody will ask, e.g.
        tests) it never waits.

        Waits without a timeout: while an update is pending the simulation
        asks within one frame. Raises RuntimeError if a question isn't for a
        newer frame than the last one answered.
        """
        self.flush(channel)
        if self._owed_answer is not None:
            channel.move_permission_queue.put(self._owed_answer)
            self._last_answered = self._owed_answer
            self._owed_answer = None

        if channel.lockstep_enabled and update_pending:
            frame = channel.move_request_queue.get()
            if self._last_answered is not None and frame <= self._last_answered:
                raise RuntimeError(
                    f"The simulation asked to move past frame {frame}, "
                    f"but frame {self._last_answered} was already answered")
            self._owed_answer = frame
            self.values_copied_while_paused = True
        else:
            self.values_copied_while_paused = False
