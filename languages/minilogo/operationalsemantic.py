from pyecore import behavior

from core.operations import operation, loop

from languages.minilogo.abstractsyntax import *

@Pen.behavior
@operation()
def evaluate(self, runtime):
    runtime.penstate.status = self.status

@Move.behavior
@operation(
    x=lambda node, runtime: node.x.evaluate(runtime),
    y=lambda node, runtime: node.y.evaluate(runtime)
)
def evaluate(self, runtime, x: int = None, y: int = None):
    start_position = runtime.penstate.position
    runtime.penstate.position = Coordinates(x=x, y=y)
    if runtime.penstate.status == PenStatus.down:
        runtime.drawing.lines.append(Line(
                color=runtime.penstate.color, 
                start=start_position, 
                end=runtime.penstate.position
            )
        )

@Color.behavior
@operation()
def evaluate(self, runtime):
    runtime.penstate.color = self.colorCode

@Variable.behavior
@operation()
def evaluate(self, runtime):
    for binding in runtime.scope.bindings:
        if binding.name == self.name:
            return binding.value
    raise Exception("Undefined variable:" + self.name)

@Assignment.behavior
@operation(value=lambda node, runtime: node.expression.evaluate(runtime))
def evaluate(self, runtime, value: any = None):
    defined = False
    for binding in runtime.scope.bindings:
        if binding.name == self.variable_name:
            binding.value = value
            defined = True
    if not defined:
        runtime.scope.bindings.append(VariableBinding(
                name=self.variable_name, 
                value=value
            )
        )

@Model.behavior
def evaluate(self, runtime):
    return loop(self.commands, lambda command: command.evaluate(runtime))

@BinaryExpression.behavior
@operation(
    left=lambda node, runtime: node.left.evaluate(runtime),
    right=lambda node, runtime: node.right.evaluate(runtime)
)
def evaluate(self, runtime, left: int = None, right: int = None):
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

@ParenthesizedExpression.behavior
def evaluate(self, runtime):
    return self.expression.evaluate(runtime)

@Literal.behavior
@operation()
def evaluate(self, runtime):
    return self.value

@RuntimeState.behavior
def initialize(self):
    self.elements = [
        Drawing(name="drawing"),
        PenState(
            name="penstate",
            color=ColorCode(r=0,g=0,b=0), 
            position=Coordinates(x=0,y=0),
            status=PenStatus.up
        ),
        Scope(name="scope")
    ]