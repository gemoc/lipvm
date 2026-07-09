"""
Load an .xmi model into memory using a pyecore Python metamodel module as the
metamodel — by default the classes in languages/sysmlv2/syntax.py.

Unlike tools/load_xmi.py (which reads an .ecore file as the metamodel), this
tool uses an existing pyecoregen-style Python module. Its EPackage is taken
from the module's ``eClass`` and registered as the metamodel, so the resulting
objects are instances of the module's own classes (e.g.
``languages.sysmlv2.syntax.PartDefinition``).

Three adjustments make such a module usable as an XMI metamodel:

  1. Reference repair. pyecoregen modules such as syntax.py declare their
     reference features without an eType, which stops pyecore from accepting
     values for them. Every untyped reference is given a permissive eType (the
     package's universal root class, e.g. ``Element``, else ``EObject``) so any
     model element can be assigned. Objects keep their real concrete classes;
     only the declared reference target types are generalised.

  2. Namespace aliasing. Tools such as Eclipse SysON serialise the model under a
     namespace URI that differs from the metamodel's nsURI. Any xmlns prefix in
     the XMI that matches the package's nsPrefix is aliased onto it.

  3. ID attribute. A domain attribute (default: ``elementId``) is promoted to an
     Ecore ID so intra-document cross-references serialised by it resolve.
     External library hrefs (e.g. ``kermllibrary:///``) stay as proxies.

Usage:
    uv run python tools/load_xmi_with_syntax.py tests/1CB-2VGR.xmi
    uv run python tools/load_xmi_with_syntax.py model.xmi -m my.pkg.syntax --tree
"""

import argparse
import importlib
import keyword
import os
import sys

from pyecore.ecore import EClass, EEnum, EObject, EReference
from pyecore.resources import ResourceSet, URI

# Allow running as a script (python tools/load_xmi_with_syntax.py) as well as
# being imported as tools.load_xmi_with_syntax.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.load_xmi import alias_namespaces, mark_id_attribute

DEFAULT_MODULE = "languages.sysmlv2.syntax"


def _all_packages(package):
    """Yields `package` and all of its (transitive) subpackages."""
    yield package
    for sub in package.eSubpackages:
        yield from _all_packages(sub)


def universal_root(packages):
    """Returns the EClass that is a supertype of every class, or None.

    Used as the permissive eType for references the metamodel leaves untyped.
    """
    classes = [c for p in packages for c in p.eClassifiers if isinstance(c, EClass)]
    for candidate in classes:
        supertypes = candidate.eAllSuperTypes()
        if all(other is candidate or candidate in other.eAllSuperTypes() for other in classes):
            return candidate
    return None


def repair_untyped_references(packages, fallback=None):
    """Assigns a permissive eType to every reference that lacks one.

    Returns (number_of_references_repaired, fallback_eclass_used).
    """
    if fallback is None:
        fallback = universal_root(packages) or EObject.eClass
    repaired = 0
    for package in packages:
        for classifier in package.eClassifiers:
            if not isinstance(classifier, EClass):
                continue
            for feature in classifier.eStructuralFeatures:
                if isinstance(feature, EReference) and feature.eType is None:
                    feature.eType = fallback
                    repaired += 1
    return repaired, fallback


def _enums(packages):
    """Returns the EEnums used as attribute types across `packages`.

    pyecoregen keeps enums as module globals whose ePackage is unset, so they
    are not in eClassifiers; they are reached through the features that use them.
    """
    enums = {}
    for package in packages:
        for classifier in package.eClassifiers:
            if not isinstance(classifier, EClass):
                continue
            for feature in classifier.eAllStructuralFeatures():
                etype = getattr(feature, "eType", None)
                if isinstance(etype, EEnum):
                    enums[id(etype)] = etype
    return list(enums.values())


def reconcile_enum_literals(packages):
    """Reverses pyecoregen's keyword-mangling of enum literal names.

    pyecoregen appends "_" to literal names that are Python keywords (in -> in_),
    but the XMI serialises the original name (in). The trailing "_" is stripped
    so those values decode; the literal's Python attribute (e.g. ``.in_``) keeps
    working. Returns the list of (enum, old_name, new_name) that were renamed.
    """
    renamed = []
    for enum in _enums(packages):
        for literal in enum.eLiterals:
            if literal.name.endswith("_") and keyword.iskeyword(literal.name[:-1]):
                old = literal.name
                literal.name = literal.name[:-1]
                renamed.append((enum.name, old, literal.name))
    return renamed


def load(xmi_path, module=DEFAULT_MODULE, id_attribute="elementId"):
    """Loads `xmi_path` using `module` as the metamodel and returns the resource.

    `module` may be a module name (str) or an already-imported module object.
    """
    if isinstance(module, str):
        module = importlib.import_module(module)
    packages = list(_all_packages(module.eClass))

    repair_untyped_references(packages)
    reconcile_enum_literals(packages)
    mark_id_attribute(packages, id_attribute)

    rset = ResourceSet()
    for package in packages:
        if package.nsURI:
            rset.metamodel_registry[package.nsURI] = package
    alias_namespaces(rset, xmi_path, packages)

    return rset.get_resource(URI(xmi_path))


def _safe_name(eobject):
    # Avoid the derived `name` feature, whose pyecoregen implementation raises.
    for attr in ("declaredName", "declaredShortName"):
        try:
            value = getattr(eobject, attr, None)
        except Exception:
            value = None
        if value:
            return value
    return None


def _print_tree(eobject, prefix="", is_last=True, is_root=True):
    name = _safe_name(eobject)
    label = eobject.eClass.name + (f" '{name}'" if name else "")
    if is_root:
        print(label)
    else:
        print(f"{prefix}{'└─ ' if is_last else '├─ '}{label}")
        prefix += "   " if is_last else "│  "
    children = list(eobject.eContents)
    for i, child in enumerate(children):
        _print_tree(child, prefix, i == len(children) - 1, is_root=False)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("xmi", help="Path to the .xmi model to load")
    parser.add_argument("-m", "--module", default=DEFAULT_MODULE,
                        help=f"Python metamodel module to use (default: {DEFAULT_MODULE})")
    parser.add_argument("--id-attribute", default="elementId",
                        help="Domain attribute to treat as an Ecore ID "
                             "(default: elementId; empty string to rely on xmi:id)")
    parser.add_argument("--tree", action="store_true",
                        help="Print the loaded containment tree")
    args = parser.parse_args()

    if not os.path.exists(args.xmi):
        parser.error(f"file not found: {args.xmi}")

    resource = load(args.xmi, args.module, args.id_attribute)
    roots = resource.contents
    object_count = sum(1 + sum(1 for _ in r.eAllContents()) for r in roots)
    module_name = roots[0].__class__.__module__ if roots else args.module
    print(f"Loaded {args.xmi} with metamodel '{args.module}': "
          f"{len(roots)} root(s), {object_count} objects.")
    print(f"Root instances are {module_name} classes "
          f"(e.g. {roots[0].eClass.name}).")

    if args.tree:
        print()
        for root in roots:
            _print_tree(root)


if __name__ == "__main__":
    main()
