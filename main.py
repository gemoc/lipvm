import sys 

from languages.minilogo.abstractsyntax import *
from languages.minilogo.operationalsemantic import *

from core.metametamodel import RuntimeState
from core.vm import VM

def main(arguments: list):
    example = Model(commands=[
        Assignment(variable_name="myvar", expression=Literal(value=10)),
        Color(colorCode=ColorCode(r=100, g=0, b=0)),
        Pen(status=PenStatus.down),
        Move(x=Literal(value=10), y=Literal(value=10)),
        Color(colorCode=ColorCode(r=0, g=100, b=0)),
        Move(x=Literal(value=20), y=Literal(value=20)),
        Color(colorCode=ColorCode(r=0, g=0, b=100)),
        Move(x=Literal(value=30), y=Literal(value=30)),
        Color(colorCode=ColorCode(r=0, g=0, b=0)),
        Move(
            x=BinaryExpression(
                left=Variable(name="myvar"), 
                operator=Operator.MULTIPLY, 
                right=Literal(value=20)), 
            y=Literal(value=30)
        ),
        Pen(status=PenStatus.up),
    ])

    runtime = RuntimeState()
    runtime.initialize()
    
    VM.start(example, runtime)

    for line in runtime.drawing.lines:
        color = "color=" + str(line.color.r) + ", " + str(line.color.g) + ", " + str(line.color.b)
        start = "start=" + str(line.start.x) + ", " + str(line.start.y)
        end = "end=" + str(line.end.x) + ", " + str(line.end.y)
        print("Line("+color + ", " + start + ", "+ end+")")

if __name__ == '__main__':
    main(sys.argv)
 