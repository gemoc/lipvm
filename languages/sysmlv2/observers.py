"""Observers on the sysmlv2 runtime registry.

They watch the runtime model (runtime.py) and report its changes to the
generic SynchronizationManager (simulation_models/synchronization.py), which
sends them to the simulation. Kept out of runtime.py, which only defines the
model, and out of facade_proxy.py, which knows nothing about SysML.
"""
from pyecore.notification import EObserver, Kind

from languages.sysmlv2.runtime import CompositeCustomValue, _custom_attribute_value


class ConfiguredValueObserver(EObserver):
    """Watches one PartInstantiation's configured values (its
    attribute_redefinitions) and records every change in the
    SynchronizationManager, converted the same way instantiation converts
    them (design doc, Topic 10 "Syncing a runtime change to the simulation").

    One observer per part, self-maintaining: on the part it reacts only to a
    redefinition being added (watch it, record its value); on a redefinition
    only to its `value` being set. Everything else is ignored, notably the
    part's observed_values, which every refresh sets: those come from the
    simulation and are never sent back. Updates always replace a value rather
    than change it in place, so nested value objects need no observers.
    """

    def __init__(self, part: "PartInstantiation", manager: "SynchronizationManager"):
        super().__init__()
        self._part = part
        self._manager = manager
        self._observed = []
        self.observe(part)
        for redefinition in part.attribute_redefinitions:
            self.observe(redefinition)

    def observe(self, notifier) -> None:
        super().observe(notifier)
        self._observed.append(notifier)

    def detach(self) -> None:
        """Stops watching the part and its redefinitions (the part was
        removed), so a later change to the detached objects isn't sent."""
        for notifier in self._observed:
            notifier.listeners.remove(self)
        self._observed = []

    def notifyChanged(self, notification):
        feature_name = notification.feature.name
        if notification.notifier is self._part:
            if notification.kind == Kind.ADD and feature_name == "attribute_redefinitions":
                redefinition = notification.new
                self.observe(redefinition)
                if redefinition.value is not None:
                    self._record(redefinition.name, redefinition.value)
        elif notification.kind == Kind.SET and feature_name == "value":
            self._record(notification.notifier.name, notification.new)

    def _record(self, attr_name: str, value: "Value") -> None:
        # Only composite values are sent, as at instantiation
        # (PartInstantiation.evaluate); a scalar has no simulation-side
        # conversion yet, so refuse it rather than drop it silently.
        if not isinstance(value, CompositeCustomValue):
            raise TypeError(
                f"Can't sync {self._part.qualified_name}'s {attr_name!r} to the simulation: "
                f"only composite values are supported, got {type(value).__name__}")
        self._manager.record_set_attribute_redefinition(self._part.qualified_name, attr_name, _custom_attribute_value(value))


class PartInstantiationTableObserver(EObserver):
    """The single entry point for watching running parts: every part in the
    registry's table of running parts (`lookup_table_part_instantiations`)
    gets its configured values watched by a ConfiguredValueObserver, both the
    parts already there when this is attached and every part added later;
    a removed part stops being watched.

    Attached once the registry is built (`Namespace.evaluate`): the parts
    already there are the startup parts, whose machines are created by their
    own path (`PartInstantiation.evaluate`), so they are only watched. A part
    added later comes from a live update, so its instantiation is also
    recorded in the SynchronizationManager, built the same way as at startup
    (`PartInstantiation.simulation_instantiation`). A part removed by a live
    update is recorded as a removal. Any other change to the table raises
    rather than leave the simulation out of step.
    """

    def __init__(self, table: "LookupTable", manager: "SynchronizationManager"):
        super().__init__()
        self._manager = manager
        self._watchers: dict[str, ConfiguredValueObserver] = {}
        self.observe(table)
        for record in table.records:
            self._watch(record.element_type)

    def notifyChanged(self, notification):
        if notification.feature.name != "records":
            return
        if notification.kind == Kind.ADD:
            part = notification.new.element_type
            self._watch(part)
            part_def_name, attrs = part.simulation_instantiation()
            self._manager.record_add_part_instantiation(part.qualified_name, part_def_name, attrs)
        elif notification.kind == Kind.REMOVE:
            qualified_name = notification.old.qualified_name
            self._watchers.pop(qualified_name).detach()
            self._manager.record_remove_part_instantiation(qualified_name)
        else:
            raise NotImplementedError(
                f"Only adding or removing one running part at a time is synced to the simulation, "
                f"got {notification.kind.name} on the part table")

    def _watch(self, part: "PartInstantiation") -> None:
        self._watchers[part.qualified_name] = ConfiguredValueObserver(part, self._manager)


def attach_registry_observers(sysml_state: "SysmlRuntimeState", manager: "SynchronizationManager") -> None:
    """Attaches every observer on the runtime registry, once it is built
    (`Namespace.evaluate`). What is in the registry now is the startup model;
    the observers watch it and report what live updates change to `manager`.

    Must run after the build pass: attached earlier, the startup elements
    would be reported as live additions. Observers for other kinds of
    elements (e.g. state usages added by live updates) belong here too.
    """
    PartInstantiationTableObserver(sysml_state.lookup_table_part_instantiations, manager)
