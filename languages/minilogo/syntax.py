from pyecore.ecore import *

from core.language import AbstractSyntaxElement, RuntimeState
from core.operations import operation, loop

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
        left=lambda node, runtime: node.left.evaluate(runtime),
        right=lambda node, runtime: node.right.evaluate(runtime)
    )
    def evaluate(self, runtime: RuntimeState, left: int = None, right: int = None) -> None:
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

    def evaluate(self, runtime: RuntimeState) -> None:
        return self.expression.evaluate(runtime)

class Terminal(Expression, metaclass=MetaEClass):
    pass

class Variable(Terminal, metaclass=MetaEClass):
    name = EAttribute(eType=EString)

    @operation()
    def evaluate(self, runtime: RuntimeState) -> None:
        for binding in runtime.scope.bindings:
            if binding.name == self.name:
                return binding.value
        raise Exception("Undefined variable:" + self.name)

class Literal(Terminal, metaclass=MetaEClass):
    value = EAttribute(eType=EInt)

    @operation()
    def evaluate(self, runtime: RuntimeState) -> None:
        return self.value

class Assignment(Command, metaclass=MetaEClass):
    variable_name = EAttribute(eType=EString)
    expression = EReference(eType=Expression, lower=1, upper=1, containment=True)

    @operation(value = lambda node, runtime: node.expression.evaluate(runtime))
    def evaluate(self, runtime: RuntimeState, value: any = None) -> None:
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

    @operation()
    def evaluate(self, runtime: RuntimeState) -> None:
        runtime.penstate.color = self.colorCode

class Move(Command, metaclass=MetaEClass):
    x = EReference(eType=Expression, lower=1, upper=1, containment=True)
    y = EReference(eType=Expression, lower=1, upper=1, containment=True)

    @operation(
        x=lambda node, runtime: node.x.evaluate(runtime),
        y=lambda node, runtime: node.y.evaluate(runtime)
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

    @operation()
    def evaluate(self, runtime: RuntimeState) -> None:
        runtime.penstate.status = self.status

class Program(AbstractSyntaxElement, metaclass=MetaEClass):
    commands = EReference(eType=Command, lower=0, upper=-1, containment=True)

    def evaluate(self, runtime: RuntimeState) -> None:

        # Initialize the runtime state when starting the execution
        runtime.elements = [
            Drawing(name="drawing"),
            PenState(
                name="penstate",
                color=ColorCode(r=0,g=0,b=0),
                position=Coordinates(x=0,y=0),
                status=PenStatus.up
            ),
            Scope(name="scope")
        ]

        return loop(self.commands, lambda command: command.evaluate(runtime))
