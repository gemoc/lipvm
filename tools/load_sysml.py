"""
Loads a .sysml model directly, by combining two previously separate steps:

  1. Model transformation: `java -jar tools/sysml-to-xmi-cli.jar <sysml> <xmi>`
     converts the textual SysML model to XMI.
  2. Model loading: tools/load_xmi_with_syntax.py loads that XMI into pyecore
     objects using a Python metamodel module (default:
     languages.sysmlv2.syntax).

This lets callers pass a .sysml path wherever they previously had to
pre-generate and pass a .xmi path.

sysml-to-xmi-cli.jar itself is too large to commit to the repo, so it isn't
checked in -- it must exist on disk locally, found via (in order):
  1. the LIPVM_SYSML_XMI_JAR environment variable, if set
  2. tools/sysml-to-xmi-cli.jar (this file's own directory), otherwise

Usage:
    uv run python tools/load_sysml.py model.sysml
    uv run python tools/load_sysml.py model.sysml -o model.xmi --tree
    uv run python tools/load_sysml.py model.sysml --no-keep-xmi
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

# Allow running as a script (python tools/load_sysml.py) as well as being
# imported as tools.load_sysml.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.load_xmi_with_syntax import DEFAULT_MODULE, _print_tree, load as load_xmi

BUNDLED_JAR = os.path.join(os.path.dirname(__file__), "sysml-to-xmi-cli.jar")
DEFAULT_JAR = os.environ.get("LIPVM_SYSML_XMI_JAR", BUNDLED_JAR)


def sysml_to_xmi(sysml_path, xmi_path=None, jar_path=DEFAULT_JAR, java_bin="java"):
    """Transforms `sysml_path` to XMI via sysml-to-xmi-cli.jar.

    The JAR's own stdout/stderr (parse warnings included) streams straight
    through, since they can point at real model issues.

    Returns the path to the generated .xmi file (`xmi_path` if given,
    otherwise `sysml_path` with its extension swapped to .xmi).
    """
    if not os.path.exists(sysml_path):
        raise FileNotFoundError(sysml_path)
    if not os.path.exists(jar_path):
        raise FileNotFoundError(
            f"sysml-to-xmi-cli.jar not found: {jar_path} -- it isn't committed to "
            f"the repo (too large). Set the LIPVM_SYSML_XMI_JAR environment "
            f"variable to its path, or place it at {BUNDLED_JAR}."
        )
    if shutil.which(java_bin) is None:
        raise RuntimeError(f"'{java_bin}' not found on PATH; the JAR needs a JRE to run")

    if xmi_path is None:
        xmi_path = os.path.splitext(sysml_path)[0] + ".xmi"

    result = subprocess.run([java_bin, "-jar", jar_path, sysml_path, xmi_path])
    if result.returncode != 0 or not os.path.exists(xmi_path):
        raise RuntimeError(
            f"sysml-to-xmi-cli.jar failed (exit {result.returncode}) "
            f"transforming {sysml_path} -> {xmi_path}"
        )
    return xmi_path


def load(sysml_path, module=DEFAULT_MODULE, id_attribute="elementId",
         xmi_path=None, jar_path=DEFAULT_JAR, keep_xmi=True):
    """Transforms `sysml_path` to XMI, then loads it with load_xmi_with_syntax.load.

    When `xmi_path` is not given, the XMI is written next to `sysml_path`
    (matching load_xmi.py's convention) unless `keep_xmi` is False, in which
    case a temp file is used and removed after loading.

    Returns the loaded pyecore resource (same as load_xmi_with_syntax.load).
    """
    use_temp = xmi_path is None and not keep_xmi
    if use_temp:
        tmp = tempfile.NamedTemporaryFile(suffix=".xmi", delete=False)
        tmp.close()
        xmi_path = tmp.name

    resolved_xmi = sysml_to_xmi(sysml_path, xmi_path, jar_path)
    try:
        return load_xmi(resolved_xmi, module, id_attribute)
    finally:
        if use_temp:
            os.remove(resolved_xmi)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("sysml", help="Path to the .sysml model to load")
    parser.add_argument("-m", "--module", default=DEFAULT_MODULE,
                        help=f"Python metamodel module to use (default: {DEFAULT_MODULE})")
    parser.add_argument("-o", "--xmi-output", dest="xmi_path", default=None,
                        help="Path for the generated .xmi "
                             "(default: <sysml> with a .xmi extension)")
    parser.add_argument("--jar", default=DEFAULT_JAR,
                        help="Path to sysml-to-xmi-cli.jar "
                             "(default: $LIPVM_SYSML_XMI_JAR if set, else "
                             f"{BUNDLED_JAR})")
    parser.add_argument("--id-attribute", default="elementId",
                        help="Domain attribute to treat as an Ecore ID "
                             "(default: elementId; empty string to rely on xmi:id)")
    parser.add_argument("--no-keep-xmi", action="store_true",
                        help="Delete the generated .xmi after loading "
                             "(ignored if -o is given)")
    parser.add_argument("--tree", action="store_true",
                        help="Print the loaded containment tree")
    args = parser.parse_args()

    if not os.path.exists(args.sysml):
        parser.error(f"file not found: {args.sysml}")

    resource = load(args.sysml, args.module, args.id_attribute,
                     args.xmi_path, args.jar, keep_xmi=not args.no_keep_xmi)
    roots = resource.contents
    object_count = sum(1 + sum(1 for _ in r.eAllContents()) for r in roots)
    module_name = roots[0].__class__.__module__ if roots else args.module
    print(f"Loaded {args.sysml} with metamodel '{args.module}': "
          f"{len(roots)} root(s), {object_count} objects.")
    print(f"Root instances are {module_name} classes "
          f"(e.g. {roots[0].eClass.name}).")

    if args.tree:
        print()
        for root in roots:
            _print_tree(root)


if __name__ == "__main__":
    main()
