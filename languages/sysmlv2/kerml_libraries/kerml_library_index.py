import json
from pathlib import Path
from typing import Dict, Optional

_LIBRARY_DIR = Path(__file__).parent
_index_cache: Optional[Dict[str, str]] = None


def _flatten(node, index: Dict[str, str]) -> None:
    if isinstance(node, dict):
        node_id = node.get('id')
        data = node.get('data')
        if node_id and isinstance(data, dict):
            declared_name = data.get('declaredName')
            if declared_name:
                index[node_id] = declared_name

        for value in node.values():
            _flatten(value, index)

    elif isinstance(node, list):
        for item in node:
            _flatten(item, index)


def load_kerml_library_index() -> Dict[str, str]:
    """
    Parses SysON's kerml.libraries JSON resources (library/kerml_libraries/*.json)
    into a flat {json-id: declaredName} lookup, so that `kermllibrary:///...#<id>`
    proxy references (e.g. Boolean, Integer) can be resolved by id without
    needing a full EMF JSON resource loader.
    """
    index: Dict[str, str] = {}

    for json_file in _LIBRARY_DIR.glob('*.json'):
        with open(json_file, encoding='utf-8') as f:
            content = json.load(f)

        _flatten(content.get('content', []), index)

    return index


def resolve_kerml_library_name(proxy_path: str) -> Optional[str]:
    """
    Resolves a `kermllibrary:///<resource>#<id>` proxy path (as found on an unresolved
    EProxy) to the declaredName of the matching library element, e.g. 'Boolean'.
    Returns None if the id isn't in any loaded library file.
    """
    global _index_cache
    if _index_cache is None:
        _index_cache = load_kerml_library_index()

    fragment = proxy_path.rsplit('#', 1)[-1]
    return _index_cache.get(fragment)
