from pyecore.ecore import *

from core.language import AbstractSyntaxElement, RuntimeState
from core.operation import Operation, lazy_loop, operation

from languages.minilogo.runtime import (
    PenStatus,
    ColorCode,
    Coordinates,
    Line,
    Drawing,
    PenState,
    Scope,
    VariableBinding,
)

# Enumerations
Operator = EEnum("Operator")
Operator.eLiterals.append(EEnumLiteral("PLUS"))
Operator.eLiterals.append(EEnumLiteral("MINUS"))
Operator.eLiterals.append(EEnumLiteral("DIVIDE"))
Operator.eLiterals.append(EEnumLiteral("MULTIPLY"))


# Abstract Syntax Classes
class Command(AbstractSyntaxElement, metaclass=MetaEClass):
    abstract = True


class Expression(AbstractSyntaxElement, metaclass=MetaEClass):
    abstract = True


class BinaryExpression(Expression, metaclass=MetaEClass):
    left = EReference(eType=Expression, lower=1, upper=1, containment=True)
    operator = EAttribute(eType=Operator)
    right = EReference(eType=Expression, lower=1, upper=1, containment=True)

    @operation(
        left=lambda self, runtime: self.left.evaluate(runtime),
        right=lambda self, runtime: self.right.evaluate(runtime)
    )
    def evaluate(self, runtime: RuntimeState, left: int = None, right: int = None) -> int:
        match self.operator:
            case Operator.PLUS:
                return left + right
            case Operator.MINUS:
                return left - right
            case Operator.DIVIDE:
                return left / right
            case Operator.MULTIPLY:
                return left * right
            case _:
                raise Exception("Unrecognized operator:" + str(self.operator))


class ParenthesizedExpression(Expression, metaclass=MetaEClass):
    expression = EReference(eType=Expression, lower=1, upper=1, containment=True)

    @operation
    def evaluate(self, runtime: RuntimeState) -> Operation:
        return self.expression.evaluate(runtime)


class Terminal(Expression, metaclass=MetaEClass):
    pass


class Variable(Terminal, metaclass=MetaEClass):
    name = EAttribute(eType=EString)

    @operation
    def evaluate(self, runtime: RuntimeState) -> int:
        for binding in runtime.scope.bindings:
            if binding.name == self.name:
                return binding.value
        raise Exception("Undefined variable:" + self.name)


class Literal(Terminal, metaclass=MetaEClass):
    value = EAttribute(eType=EInt)

    @operation
    def evaluate(self, runtime: RuntimeState) -> int:
        return self.value


class Assignment(Command, metaclass=MetaEClass):
    variable_name = EAttribute(eType=EString)
    expression = EReference(eType=Expression, lower=1, upper=1, containment=True)

    @operation(value=lambda self, runtime: self.expression.evaluate(runtime))
    def evaluate(self, runtime: RuntimeState, value: int = None) -> None:
        defined = False
        for binding in runtime.scope.bindings:
            if binding.name == self.variable_name:
                binding.value = value
                defined = True
        if not defined:
            runtime.scope.bindings.append(VariableBinding(
                name=self.variable_name,
                value=value
            ))


class Color(Command, metaclass=MetaEClass):
    colorCode = EReference(eType=ColorCode, lower=1, upper=1, containment=False)

    @operation
    def evaluate(self, runtime: RuntimeState) -> None:
        runtime.penstate.color = self.colorCode


class Move(Command, metaclass=MetaEClass):
    x = EReference(eType=Expression, lower=1, upper=1, containment=True)
    y = EReference(eType=Expression, lower=1, upper=1, containment=True)

    @operation(
        x=lambda self, runtime: self.x.evaluate(runtime),
        y=lambda self, runtime: self.y.evaluate(runtime)
    )
    def evaluate(self, runtime: RuntimeState, x: int = None, y: int = None) -> None:
        start_position = runtime.penstate.position
        runtime.penstate.position = Coordinates(x=x, y=y)
        if runtime.penstate.status == PenStatus.down:
            runtime.drawing.lines.append(Line(
                    color=runtime.penstate.color,
                    start=start_position,
                    end=runtime.penstate.position
                    )
                )


class Pen(Command, metaclass=MetaEClass):
    status = EAttribute(eType=PenStatus)

    @operation
    def evaluate(self, runtime: RuntimeState) -> None:
        runtime.penstate.status = self.status


class Program(AbstractSyntaxElement, metaclass=MetaEClass):
    commands = EReference(eType=Command, lower=0, upper=-1, containment=True)

    @operation
    def evaluate(self, runtime: RuntimeState) -> Operation:
        runtime.elements = [
            Drawing(name="drawing"),
            PenState(
                name="penstate",
                color=ColorCode(r=0, g=0, b=0),
                position=Coordinates(x=0, y=0),
                status=PenStatus.up
            ),
            Scope(name="scope")
        ]
        return lazy_loop(self.commands, lambda cmd, rt: cmd.evaluate(rt), args=(runtime,))
