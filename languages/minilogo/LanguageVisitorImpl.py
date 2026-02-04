from antlr4 import *
from copy import deepcopy

from backend.annotation import step
from backend.interpreter import Interpreter

from languages.minilogo.LanguageParser import LanguageParser

class LanguageVisitorImpl(ParseTreeVisitor):
    """
    Language Visitor, an AST visitor of the language defined by the language designer.

    Implementation constraints:

    - When visiting subtrees, use the visit(node) and visitChildren() methods from the interpreter.
    - Store all the data related to the execution in interpreter.environment, as attributes.
    """

    def __init__(self, interpreter: Interpreter):
        super().__init__()

        # Initial configuration
        self._interpreter = interpreter
        self._environment = interpreter.environment

        # State of minilogo
        self._environment.color = "#FFFFFF"
        self._environment.pen_coordinates = (0, 0)
        self._environment.pen_up = True
        self._environment.lines = []

        # State of execution
        self._environment.sp = -1  # Scope pointer
        self._environment.scopes = [None] * 100  # Closure scopes
        self._environment.functions = {}

    def visitVariable(self, ctx: LanguageParser.VariableContext):
        if not ctx.ID().getText() in self._environment.scopes[self._environment.sp]:
            raise Exception("Undefined variable: " + str(ctx.ID().getText()))
        return self._environment.scopes[self._environment.sp][ctx.ID().getText()]

    def visitLiteral(self, ctx: LanguageParser.LiteralContext):
        if ctx.variable() is not None:
            return self._interpreter.visit(ctx.variable())
        return int(ctx.NUMBER().getText())

    def visitExpression(self, ctx: LanguageParser.ExpressionContext):
        if ctx.leftOperand is not None and ctx.rightOperand is not None:
            left = self._interpreter.visit(ctx.leftOperand)
            right = self._interpreter.visit(ctx.rightOperand)
            match ctx.OPERATOR().getText():
                case "+":
                    return left + right
                case "-":
                    return left - right
                case "*":
                    return left * right
                case "/":
                    return left / right
                case _:
                    raise Exception("Unknown operator: " + str(ctx.OPERATOR().getText()))
        if ctx.literal() is not None:
            return self._interpreter.visit(ctx.literal())
        if ctx.expression(0) is not None:
            return self._interpreter.visit(ctx.expression(0))
        raise Exception("Unrecognized expression: " + str(ctx))

    def visitArguments(self, ctx: LanguageParser.ArgumentsContext):
        return [self._interpreter.visit(arg) for arg in ctx.expression()]

    @step
    def visitMove(self, ctx: LanguageParser.MoveContext):
        x = self._interpreter.visit(ctx.expression(0))
        y = self._interpreter.visit(ctx.expression(1))

        if not self._environment.pen_up:
            self._environment.lines.append((self._environment.pen_coordinates, (x, y), self._environment.color))

        self._environment.pen_coordinates = (x, y)

    def visitColor(self, ctx: LanguageParser.ColorContext):
        self._environment.color = ctx.COLOR().getText()

    def visitPen(self, ctx: LanguageParser.PenContext):
        self._environment.pen_up = ctx.status.text == "up"

    def visitHalt(self, ctx: LanguageParser.HaltContext):
        self._interpreter.halt()

    def visitCall(self, ctx: LanguageParser.CallContext):
        if not ctx.ID().getText() in self._environment.functions:
            raise Exception("Undefined function: " + str(ctx.ID().getText()))

        parameters = self._environment.functions[ctx.ID().getText()][0]
        body = self._environment.functions[ctx.ID().getText()][1]
        arguments = []

        if len(parameters) > 0:
            arguments = self._interpreter.visit(ctx.arguments())
            if len(parameters) != len(arguments):
                raise Exception("Unexpected number of arguments: " + str(len(ctx.arguments())))

        # Creating a lexical closure
        self._environment.scopes[self._environment.sp + 1] = deepcopy(self._environment.scopes[self._environment.sp])
        self._environment.sp += 1

        # Binding arguments with parameters
        for i in range(len(parameters)):
            self._environment.scopes[self._environment.sp][parameters[i]] = arguments[i]

        # Interpret the body of the function
        self._interpreter.visit(body)

        # Return to previous scope
        self._environment.sp -= 1

    def visitDef(self, ctx: LanguageParser.DefContext):
        if ctx.parameters() is not None:
            self._environment.functions[ctx.ID().getText()] = (self._interpreter.visit(ctx.parameters()), ctx.body())
        else:
            self._environment.functions[ctx.ID().getText()] = ([], ctx.body())

    def visitParameters(self, ctx: LanguageParser.ParametersContext):
        return [param.getText() for param in ctx.ID()]

    def visitBody(self, ctx: LanguageParser.BodyContext):
        return self._interpreter.visitChildren(ctx)

    def visitAssignment(self, ctx: LanguageParser.AssignmentContext):
        self._environment.scopes[self._environment.sp][ctx.ID().getText()] = self._interpreter.visit(ctx.expression())
        return self._environment.scopes[self._environment.sp][ctx.ID().getText()]

    def visitForloop(self, ctx: LanguageParser.ForloopContext):
        if ctx.assignment() is not None:
            iterator = self._interpreter.visit(ctx.assignment())
            variable = ctx.assignment().ID().getText()
        elif ctx.variable() is not None:
            iterator = self._interpreter.visit(ctx.variable())
            variable = ctx.variable().ID().getText()
        else:
            raise Exception("Cannot resolve iterator: " + str(ctx))

        if ctx.expression() is None:
            raise Exception("Undefined boundary in for loop: " + str(ctx))

        for iterator in range(self._interpreter.visit(ctx.expression())):
            self._environment.scopes[self._environment.sp][variable] = iterator
            self._interpreter.visit(ctx.body())

    def visitMain(self, ctx: LanguageParser.MainContext):
        self._environment.sp = 0
        self._environment.scopes[self._environment.sp] = {}
        self._interpreter.visitChildren(ctx)



del LanguageParser