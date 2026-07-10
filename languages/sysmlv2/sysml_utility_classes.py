
def qualified_name(o) -> str:
    parts = []
    current = o
    while current is not None:
        name = getattr(current, 'declaredName', None)
        if name:
            parts.append(name)
        current = current.eContainer()
    return '::'.join(reversed(parts))