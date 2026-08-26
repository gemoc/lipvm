from pyecore.ecore import EEnum

# Plain pyecore EEnums, not Python enum.Enum subclasses — EAttribute(eType=...)
# requires an EClassifier (EEnum), which a Python Enum class isn't.
TypeKind = EEnum('TypeKind', literals=['SCALAR', 'PART', 'ITEM', 'ACTION', 'CUSTOM', 'ENUM', 'UNKNOWN'])

ParamDirection = EEnum('ParamDirection', literals=['IN', 'OUT', 'INOUT'])

ScalarType = EEnum('ScalarType', literals=['NONE', 'BOOLEAN', 'INTEGER', 'REAL', 'STRING'])

# Only the scalar names ScalarValues.json actually declares are mapped;
# names outside this set (e.g. Rational, Natural, Complex) still get a
# SCALAR TypeRef, just with scalar_type left unset.
_SCALAR_TYPE_BY_NAME = {
    'Boolean': ScalarType.BOOLEAN,
    'String': ScalarType.STRING,
    'Integer': ScalarType.INTEGER,
    'Real': ScalarType.REAL,
}

# Converts a LiteralValue's string `el` back to the Python type its
# scalar_type names -- the inverse of _literal_value()'s str(node.value)
# encoding in syntax.py. BOOLEAN/INTEGER/REAL are the only ones a
# CompositeCustomValue's elements need converted; STRING/NONE pass el
# through unchanged (the default), since it's already the right shape.
_LITERAL_PYTHON_CONVERTERS = {
    ScalarType.BOOLEAN: lambda s: s == "True",
    ScalarType.INTEGER: int,
    ScalarType.REAL: float,
}

# Operators actually used by `accept when` conditions in today's models
# (confirmed by inspecting both test .xmi files) -- not an attempt to cover
# every OperatorExpression operator SysML allows, just what's needed now;
# extending this table is all a new operator needs.
_BINARY_OPERATORS = {
    "==": lambda left, right: left == right,
    "and": lambda left, right: left and right,
    "or": lambda left, right: left or right,
    "!=": lambda left, right: not(left == right),
    ">=": lambda left, right: left >= right,
    ">": lambda left, right: left > right,
    "<=": lambda left, right: left <= right,
    "<": lambda left, right: left < right,
}