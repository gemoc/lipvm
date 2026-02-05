from antlr4 import *
from copy import deepcopy

from backend.annotation import step
from backend.interpreter import Interpreter

from languages.minilogo.LanguageParser import LanguageParser

class LanguageInterpreter(Interpreter):
    """
    An AST visitor interpreting the language defined by the language designer.

    Implementation constraints:

    - When visiting subtrees, use the yield self.visit(node) and yield self.visitChildren() methods.
    - Use yield keyword instead of return, when defining the return value of a method.
    - Store all the data related to the execution in interpreter.environment, as attributes.
    """

    def __init__(self, parser: Parser):
        super().__init__(parser)

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
        yield self._environment.scopes[self._environment.sp][ctx.ID().getText()]

    def visitLiteral(self, ctx: LanguageParser.LiteralContext):
        if ctx.variable() is not None:
            yield self.visit(ctx.variable())
        else:
            yield int(ctx.NUMBER().getText())

    def visitExpression(self, ctx: LanguageParser.ExpressionContext):
        if ctx.leftOperand is not None and ctx.rightOperand is not None:

            left = yield self.visit(ctx.leftOperand)
            right = yield self.visit(ctx.rightOperand)

            match ctx.OPERATOR().getText():
                case "+": yield left + right
                case "-": yield left - right
                case "*": yield left * right
                case "/": yield left / right
                case _:
                    raise Exception("Unknown operator: " + str(ctx.OPERATOR().getText()))

        elif ctx.literal() is not None:
            yield self.visit(ctx.literal())

        elif ctx.expression(0) is not None:
            yield self.visit(ctx.expression(0))

        else:
            raise Exception("Unrecognized expression: " + str(ctx))

    def visitArguments(self, ctx: LanguageParser.ArgumentsContext):
        arguments = []
        for arg_node in ctx.expression():
            arg = yield self.visit(arg_node)
            arguments.append(arg)
        yield arguments

    @step
    def visitMove(self, ctx: LanguageParser.MoveContext):
        x = yield self.visit(ctx.expression(0))
        y = yield self.visit(ctx.expression(1))

        if not self._environment.pen_up:
            self._environment.lines.append((self._environment.pen_coordinates, (x, y), self._environment.color))

        self._environment.pen_coordinates = (x, y)

    def visitColor(self, ctx: LanguageParser.ColorContext):
        self._environment.color = ctx.COLOR().getText()

    def visitPen(self, ctx: LanguageParser.PenContext):
        self._environment.pen_up = ctx.status.text == "up"

    def visitHalt(self, ctx: LanguageParser.HaltContext):
        self.halt()

    def visitCall(self, ctx: LanguageParser.CallContext):
        if not ctx.ID().getText() in self._environment.functions:
            raise Exception("Undefined function: " + str(ctx.ID().getText()))

        parameters = self._environment.functions[ctx.ID().getText()][0]
        body = self._environment.functions[ctx.ID().getText()][1]
        arguments = []

        if len(parameters) > 0:
            arguments = yield self.visit(ctx.arguments())
            if len(parameters) != len(arguments):
                raise Exception("Unexpected number of arguments: " + str(len(ctx.arguments())))

        # Creating a lexical closure
        self._open_closure()

        # Binding arguments with parameters
        for i in range(len(parameters)):
            self._environment.scopes[self._environment.sp][parameters[i]] = arguments[i]

        # Interpret the body of the function
        yield self.visit(body)

        # Return to previous scope
        self._close_closure()

    def _open_closure(self):
        self._environment.scopes[self._environment.sp + 1] = deepcopy(self._environment.scopes[self._environment.sp])
        self._environment.sp += 1

    def _close_closure(self):
        self._environment.sp -= 1

    def visitDef(self, ctx: LanguageParser.DefContext):
        if ctx.parameters() is not None:
            parameters = yield self.visit(ctx.parameters())
            self._environment.functions[ctx.ID().getText()] = (parameters, ctx.body())
        else:
            self._environment.functions[ctx.ID().getText()] = ([], ctx.body())

    def visitParameters(self, ctx: LanguageParser.ParametersContext):
        yield [param.getText() for param in ctx.ID()]

    def visitBody(self, ctx: LanguageParser.BodyContext):
        yield self.visitChildren(ctx)

    def visitAssignment(self, ctx: LanguageParser.AssignmentContext):
        self._environment.scopes[self._environment.sp][ctx.ID().getText()] = yield self.visit(ctx.expression())
        yield self._environment.scopes[self._environment.sp][ctx.ID().getText()]

    def visitForloop(self, ctx: LanguageParser.ForloopContext):
        self._open_closure()
        if ctx.assignment() is not None:
            iterator = yield self.visit(ctx.assignment())
            variable = ctx.assignment().ID().getText()
        elif ctx.variable() is not None:
            iterator = yield self.visit(ctx.variable())
            variable = ctx.variable().ID().getText()
        else:
            raise Exception("Cannot resolve iterator: " + str(ctx))

        if ctx.expression() is None:
            raise Exception("Undefined boundary in for loop: " + str(ctx))

        limit = yield self.visit(ctx.expression())
        for iterator in range(limit):
            self._environment.scopes[self._environment.sp][variable] = iterator
            yield self.visit(ctx.body())
        self._close_closure()

    def visitMain(self, ctx: LanguageParser.MainContext):
        self._environment.sp = 0
        self._environment.scopes[self._environment.sp] = {}
        yield self.visitChildren(ctx)

del LanguageParser