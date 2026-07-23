import functools
import importlib
import inspect
import pkgutil

from languages.sysmlv2 import simulation_models


@functools.lru_cache()
def scan_for_subclasses(base_class: type) -> dict:
    """Maps each concrete subclass of `base_class`'s name to the class
    itself, discovered by recursively scanning every module in the
    simulation_models package tree (including subpackages, e.g.
    fischertechnik, and any future sibling like water_power_plant).
    Computed once per (process, base_class) and cached, since the scan/
    import work has no reason to repeat.
    """
    registry = {}
    for _, module_name, _ in pkgutil.walk_packages(simulation_models.__path__, simulation_models.__name__ + "."):
        module = importlib.import_module(module_name)
        for class_name, klass in inspect.getmembers(module, inspect.isclass):
            if issubclass(klass, base_class) and klass is not base_class:
                registry[class_name] = klass
    return registry
