"""
Load an .xmi model against a set of .ecore metamodels and (by default) emit a
Python script that recreates the model with pyecore.

The tool:

  1. Loads every given .ecore file and registers its EPackage(s) in a
     ResourceSet's metamodel registry, keyed by nsURI.

  2. Reconciles the namespaces declared in the .xmi with the loaded packages.
     Tools such as Eclipse SysON serialise models under a namespace URI that
     differs from the metamodel's nsURI (e.g. the XMI uses
     "http://www.eclipse.org/syson/sysml" while the .ecore declares
     "https://www.omg.org/spec/SysML/20250201"). Any xmlns prefix in the XMI
     that matches a loaded package's nsPrefix is aliased onto that package so
     the model can be resolved.

  3. Optionally promotes a domain attribute (default: "elementId") to an Ecore
     "ID" attribute so that intra-document cross-references serialised by that
     attribute resolve. Standard xmi:id based models do not need this.

  4. Loads the .xmi. Unresolvable external references (e.g. "kermllibrary:///"
     library hrefs) are kept as pyecore proxies and never dereferenced.

By default a Python file reproducing the model is written next to the .xmi.
Pass --no-codegen to only validate that the model loads.

The generated script reloads the .ecore metamodels by default. Pass -m/--module
to make it import an existing Python metamodel implementation instead (e.g. the
pyecoregen-based languages.sysmlv2.syntax). Reference features that such a module
leaves without an eType are repaired for the elements the model actually uses, so
the recreation runs without touching the .ecore at all.

Usage:
    uv run python tools/load_xmi.py tests/1CB-2VGR.xmi \
        -e languages/sysmlv2/SysML.ecore

    uv run python tools/load_xmi.py tests/1CB-2VGR.xmi \
        -e languages/sysmlv2/SysML.ecore -m languages.sysmlv2.syntax

    uv run python tools/load_xmi.py model.xmi -e a.ecore -e b.ecore \
        -o rebuild_model.py
"""

import argparse
import keyword
import os
import re
from xml.etree import ElementTree

from pyecore.ecore import EAttribute, EClass, EEnum, EProxy, EReference
from pyecore.resources import ResourceSet, URI


# --------------------------------------------------------------------------- #
# Metamodel loading / registration
# --------------------------------------------------------------------------- #

def _all_packages(package):
    """Yields `package` and all of its (transitive) subpackages."""
    yield package
    for sub in package.eSubpackages:
        yield from _all_packages(sub)


def register_metamodels(rset, ecore_paths):
    """Loads each .ecore file and registers its packages by nsURI.

    Returns the flat list of every EPackage (including subpackages) found.
    """
    packages = []
    for path in ecore_paths:
        root = rset.get_resource(URI(path)).contents[0]
        for package in _all_packages(root):
            if package.nsURI:
                rset.metamodel_registry[package.nsURI] = package
            packages.append(package)
    return packages


def _xmi_namespaces(xmi_path):
    """Returns the {prefix: uri} xmlns declarations on the XMI root element."""
    namespaces = {}
    for event, (prefix, uri) in ElementTree.iterparse(xmi_path, events=["start-ns"]):
        namespaces.setdefault(prefix, uri)
    return namespaces


def alias_namespaces(rset, xmi_path, packages):
    """Aliases XMI namespaces onto loaded packages when the nsURI differs.

    Matching is done by nsPrefix: an xmlns prefix declared in the XMI that
    equals a loaded package's nsPrefix but points at a different URI is
    registered as an additional key for that package. Returns the mapping of
    {xmi_uri: package} that was added, so codegen can reproduce it.
    """
    by_prefix = {p.nsPrefix: p for p in packages if p.nsPrefix}
    aliases = {}
    for prefix, uri in _xmi_namespaces(xmi_path).items():
        if uri in rset.metamodel_registry:
            continue
        package = by_prefix.get(prefix)
        if package is not None:
            rset.metamodel_registry[uri] = package
            aliases[uri] = package
    return aliases


def mark_id_attribute(packages, attribute_name):
    """Promotes every attribute named `attribute_name` to an Ecore ID.

    pyecore populates its uuid lookup table from attributes whose `iD` flag is
    set, which is what lets cross-references serialised by that attribute
    resolve during load.
    """
    if not attribute_name:
        return
    for package in packages:
        for classifier in package.eClassifiers:
            if not isinstance(classifier, EClass):
                continue
            for feature in classifier.eAllStructuralFeatures():
                if isinstance(feature, EAttribute) and feature.name == attribute_name:
                    feature.iD = True


def load_model(xmi_path, ecore_paths, id_attribute="elementId"):
    """Loads `xmi_path` against `ecore_paths`.

    Returns (resource, packages, aliases).
    """
    rset = ResourceSet()
    packages = register_metamodels(rset, ecore_paths)
    aliases = alias_namespaces(rset, xmi_path, packages)
    mark_id_attribute(packages, id_attribute)
    resource = rset.get_resource(URI(xmi_path))
    return resource, packages, aliases


# --------------------------------------------------------------------------- #
# Code generation
# --------------------------------------------------------------------------- #

def _var_name(eobject, name):
    base = re.sub(r"[^0-9a-zA-Z]", "_", eobject.eClass.name).lower()
    if not base or base[0].isdigit():
        base = "e_" + base
    if keyword.iskeyword(base):
        base += "_"
    return f"{base}_{name}"


class _CodeGenerator:
    def __init__(self, resource, ecore_paths, aliases, id_attribute, modules=None):
        self.resource = resource
        self.ecore_paths = ecore_paths
        self.aliases = aliases
        self.id_attribute = id_attribute
        self.modules = list(modules or [])   # Python modules to import instead
        self.var = {}          # id(eobject) -> variable name
        self.wired = set()     # (id(src), feature name, id(target)) done pairs
        self.used = {}         # classifier name -> classifier (to bind once)
        self.ref_fixes = {}    # (declaring class, ref name) -> target type name
        self.needs_from_string = False

    def _literal(self, feature, value):
        """Returns a Python expression recreating an attribute value, or None.

        Enum classifiers are recorded so they get bound alongside the classes
        and can be referenced directly (e.g. ``VisibilityKind.getEEnumLiteral``).
        """
        etype = feature.eType
        if isinstance(etype, EEnum):
            self.used[etype.name] = etype
            if self.modules:
                # A generated module (e.g. pyecoregen) may rename literals that
                # clash with Python keywords (in -> in_); look up by ordinal.
                return f"{etype.name}.getEEnumLiteral(value={value.value})"
            return f"{etype.name}.getEEnumLiteral({value.name!r})"
        if isinstance(value, bool):
            return "True" if value else "False"
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, str):
            return repr(value)
        # Fall back to the metamodel's string serialisation.
        self.needs_from_string = True
        return f"_from_string({etype.name!r}, {etype.to_string(value)!r})"

    def _record_ref_fix(self, feature):
        """Remembers a reference's declaring class and target type.

        Modules such as languages/sysmlv2/syntax.py declare reference features
        without an eType, which stops pyecore from accepting values for them.
        The generated script restores the eTypes this model actually uses.
        """
        owner = feature.eContainingClass
        etype = feature.eType
        if owner is not None and etype is not None:
            self.ref_fixes[(owner.name, feature.name)] = etype.name

    # -- object discovery --------------------------------------------------- #

    def _all_objects(self):
        objects = []
        for root in self.resource.contents:
            objects.append(root)
            objects.extend(root.eAllContents())
        return objects

    def _assign_names(self, objects):
        for i, obj in enumerate(objects):
            self.var[id(obj)] = _var_name(obj, str(i))

    # -- code sections ------------------------------------------------------ #

    def _preamble(self):
        if self.modules:
            return self._module_preamble()
        return self._ecore_preamble()

    def _find_helper(self):
        return [
            "",
            "",
            "def _find(name):",
            "    for _p in _packages:",
            "        classifier = _p.getEClassifier(name)",
            "        if classifier is not None:",
            "            return classifier",
            "    raise KeyError('Unknown classifier: ' + name)",
        ]

    def _from_string_helper(self):
        if not self.needs_from_string:
            return []
        return [
            "",
            "",
            "def _from_string(type_name, text):",
            "    return _find(type_name).from_string(text)",
        ]

    def _ecore_preamble(self):
        lines = [
            '"""Auto-generated by tools/load_xmi.py — recreates the loaded model."""',
            "",
            "from pyecore.resources import ResourceSet, URI",
            "",
            "",
            "def _all_packages(package):",
            "    yield package",
            "    for sub in package.eSubpackages:",
            "        yield from _all_packages(sub)",
            "",
            "",
            "rset = ResourceSet()",
            "_packages = []",
        ]
        for path in self.ecore_paths:
            lines.append(f"for _p in _all_packages(rset.get_resource(URI({path!r})).contents[0]):")
            lines.append("    if _p.nsURI:")
            lines.append("        rset.metamodel_registry[_p.nsURI] = _p")
            lines.append("    _packages.append(_p)")
        for uri, package in self.aliases.items():
            lines.append(
                f"rset.metamodel_registry[{uri!r}] = "
                f"next(p for p in _packages if p.nsURI == {package.nsURI!r})"
            )
        lines += self._find_helper()
        lines += self._from_string_helper()
        lines.append("")
        return lines

    def _module_preamble(self):
        lines = [
            '"""Auto-generated by tools/load_xmi.py — recreates the loaded model."""',
            "",
        ]
        for module in self.modules:
            lines.append(f"from {module} import *")
        # _find/_packages are only needed for the rare string-serialised
        # attribute fallback; everything else uses the imported classes directly.
        if self.needs_from_string:
            lines.append("")
            for i, module in enumerate(self.modules):
                lines.append(f"import {module} as _mod_{i}")
            packages = ", ".join(f"_mod_{i}.eClass" for i in range(len(self.modules)))
            lines.append(f"_packages = [{packages}]")
            lines += self._find_helper()
            lines += self._from_string_helper()
        lines.append("")
        return lines

    def _classifier_bindings(self):
        """Binds every used classifier name to its EClass/EEnum, once each.

        In module mode the classifiers are already available as module globals
        (via ``from <module> import *``), so no binding is emitted.
        """
        if self.modules:
            return []
        lines = ["", "# --- Classifiers ---"]
        for name in sorted(self.used):
            lines.append(f"{name} = _find({name!r})")
        return lines

    def _reference_fixes(self):
        """Restores reference eTypes missing from the imported module(s).

        Uses the imported classes directly, e.g. ``Element.ownedRelationship``
        (the class-level EReference) and ``Relationship`` (its target class).
        """
        if not self.modules or not self.ref_fixes:
            return []
        lines = [
            "",
            "# --- Reference type repair ---",
            "# The imported module(s) declare these references without an eType;",
            "# restore the ones this model uses so values can be assigned.",
            "",
            "",
            "def _fix(feature, target_type):",
            "    if feature.eType is None:",
            "        feature.eType = target_type",
            "",
        ]
        for (cls, feat), type_name in sorted(self.ref_fixes.items()):
            if feat.isidentifier() and not keyword.iskeyword(feat):
                reference = f"{cls}.{feat}"
            else:
                reference = f"getattr({cls}, {feat!r})"
            lines.append(f"_fix({reference}, {type_name})")
        return lines

    def _creation(self, objects):
        lines = ["", "# --- Object creation and attributes ---"]
        for obj in objects:
            var = self.var[id(obj)]
            self.used[obj.eClass.name] = obj.eClass
            kwargs = []
            extra = []
            for feature in obj.eClass.eAllStructuralFeatures():
                if not isinstance(feature, EAttribute):
                    continue
                if feature.derived or not feature.changeable:
                    continue
                if not obj.eIsSet(feature):
                    continue
                value = obj.eGet(feature)
                if feature.many:
                    items = [self._literal(feature, v) for v in value]
                    items = [x for x in items if x is not None]
                    if not items:
                        continue
                    literal = f"[{', '.join(items)}]"
                else:
                    literal = self._literal(feature, value)
                    if literal is None:
                        continue
                name = feature.name
                if name.isidentifier() and not keyword.iskeyword(name):
                    kwargs.append(f"{name}={literal}")
                else:
                    # Feature name is not a usable Python keyword argument.
                    extra.append(f"setattr({var}, {name!r}, {literal})")
            lines.append(f"{var} = {obj.eClass.name}({', '.join(kwargs)})")
            lines.extend(extra)
        return lines

    def _containment(self, objects):
        lines = ["", "# --- Containment (model tree) ---"]
        for obj in objects:
            container = obj.eContainer()
            if container is None:
                continue
            feature = obj.eContainmentFeature()
            if feature is None:
                continue
            self._record_ref_fix(feature)
            parent = self.var[id(container)]
            child = self.var[id(obj)]
            if feature.many:
                lines.append(f"{parent}.{feature.name}.append({child})")
            else:
                lines.append(f"{parent}.{feature.name} = {child}")
        return lines

    def _cross_references(self, objects):
        lines = ["", "# --- Cross references ---"]
        for obj in objects:
            src = self.var[id(obj)]
            for feature in obj.eClass.eAllStructuralFeatures():
                if not isinstance(feature, EReference):
                    continue
                if feature.containment or feature.container:
                    continue
                if feature.derived or not feature.changeable:
                    continue
                if not obj.eIsSet(feature):
                    continue
                value = obj.eGet(feature)
                targets = list(value) if feature.many else [value]
                for target in targets:
                    if target is None:
                        continue
                    line = self._reference_line(obj, src, feature, target)
                    if line is not None:
                        lines.append(line)
        return lines

    def _reference_line(self, obj, src, feature, target):
        # External / unresolved references are kept as proxies: emit a comment
        # documenting the href rather than trying (and failing) to recreate it.
        if isinstance(target, EProxy) and not target.resolved:
            return f"# {src}.{feature.name} -> external proxy {target._proxy_path!r}"

        tid = id(target)
        if tid not in self.var:
            return f"# {src}.{feature.name} -> object outside this resource (skipped)"

        # Avoid wiring both ends of a bidirectional reference twice.
        pair = tuple(sorted((id(obj), tid))) + (feature.name,)
        opposite = feature.eOpposite
        if opposite is not None:
            pair = tuple(sorted((id(obj), tid))) + tuple(sorted((feature.name, opposite.name)))
        if pair in self.wired:
            return None
        self.wired.add(pair)
        self._record_ref_fix(feature)

        dst = self.var[tid]
        if feature.many:
            return f"{src}.{feature.name}.append({dst})"
        return f"{src}.{feature.name} = {dst}"

    def _footer(self):
        roots = [self.var[id(r)] for r in self.resource.contents]
        return [
            "",
            "# --- Model roots ---",
            f"roots = [{', '.join(roots)}]",
        ]

    def generate(self):
        objects = self._all_objects()
        self._assign_names(objects)
        # Build the creation section first: it records which classifiers are
        # used (via self.used), which the binding section then declares upfront.
        creation = self._creation(objects)
        containment = self._containment(objects)
        cross = self._cross_references(objects)
        lines = []
        lines += self._preamble()
        lines += self._classifier_bindings()
        lines += self._reference_fixes()
        lines += creation
        lines += containment
        lines += cross
        lines += self._footer()
        return "\n".join(lines) + "\n"


def generate_python(resource, ecore_paths, aliases, id_attribute, modules=None):
    return _CodeGenerator(resource, ecore_paths, aliases, id_attribute, modules).generate()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xmi", help="Path to the .xmi model to load")
    parser.add_argument("-e", "--ecore", action="append", default=[], required=True,
                        metavar="ECORE",
                        help="An .ecore metamodel the XMI depends on (repeatable)")
    parser.add_argument("-o", "--output", default=None,
                        help="Path of the generated Python file "
                             "(default: <xmi> with a .py extension)")
    parser.add_argument("-m", "--module", action="append", default=[],
                        metavar="MODULE",
                        help="Python module providing the metamodel classes for "
                             "the generated script to import instead of reloading "
                             "the .ecore (e.g. languages.sysmlv2.syntax; "
                             "repeatable). References missing an eType in the "
                             "module are repaired for the elements this model uses.")
    parser.add_argument("--id-attribute", default="elementId",
                        help="Domain attribute to treat as an Ecore ID for "
                             "reference resolution (default: elementId; pass "
                             "an empty string to rely solely on xmi:id)")
    parser.add_argument("--no-codegen", action="store_true",
                        help="Only load and validate the model; do not emit code")
    args = parser.parse_args()

    for path in [args.xmi, *args.ecore]:
        if not os.path.exists(path):
            parser.error(f"file not found: {path}")

    resource, _packages, aliases = load_model(args.xmi, args.ecore, args.id_attribute)
    object_count = sum(1 + sum(1 for _ in r.eAllContents()) for r in resource.contents)
    print(f"Loaded {args.xmi}: {len(resource.contents)} root(s), {object_count} objects.")
    if aliases:
        for uri, package in aliases.items():
            print(f"  aliased namespace {uri} -> package {package.name} ({package.nsURI})")

    if args.no_codegen:
        return

    output = args.output or os.path.splitext(args.xmi)[0] + ".py"
    code = generate_python(resource, args.ecore, aliases, args.id_attribute, args.module)
    with open(output, "w") as f:
        f.write(code)
    print(f"Model recreation code written to {output}")


if __name__ == "__main__":
    main()
