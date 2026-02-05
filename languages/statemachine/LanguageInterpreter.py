from antlr4 import *
from copy import deepcopy

from backend.annotation import step
from backend.interpreter import Interpreter

from languages.statemachine.LanguageParser import LanguageParser

class State:

    def __init__(self, name):
        self._name = name
        self._transitions = {}
        self._activation_function = None

    def __str__(self):
        return self._name

    def add_transition(self, name, state_name):
        self._transitions[name] = state_name

    def add_activation_function(self, body):
        self._activation_function = body

    @property
    def name(self):
        return self._name

    @property
    def transitions(self):
        return self._transitions

    @property
    def activation_function(self):
        return self._activation_function

class Machine:

    def __init__(self, name):
        self._name = name
        self._events = []
        self._states = {}
        self._initial_state = None

    def add_event(self, name):
        self._events.append(name)

    def add_state(self, name, state):
        self._states[name] = state

    def add_initial_state(self, name):
        self._initial_state = name

    @property
    def name(self):
        return self._name

    @property
    def events(self):
        return self._events

    @property
    def states(self):
        return self._states

    @property
    def initial_state(self):
        return self._initial_state

class LanguageInterpreter(Interpreter):

    def __init__(self, parser: Parser):
        super().__init__(parser)

        # Initializing machines
        self._environment.machine = None
        self._environment.current_state = None

        # State of execution
        self._environment.sp = -1                # Scope pointer
        self._environment.scopes = [None] * 100  # Closure scopes
        self._environment.primitives = {}        # Supported primitive functions

        # Primitives
        self._environment.primitives["print"] = lambda x: print(x)

    def visitMachine(self, ctx:LanguageParser.MachineContext):
        self._environment.machine = Machine(ctx.ID().getText())

    def visitEvents(self, ctx:LanguageParser.EventsContext):
        events = [param.getText() for param in ctx.ID()]
        for event in events:
           self._environment.machine.add_event(event)

    def visitInitial(self, ctx:LanguageParser.InitialContext):
        self._environment.machine.add_initial_state(ctx.ID().getText())

    def visitState(self, ctx:LanguageParser.StateContext):
        state = State(ctx.ID().getText())
        self._environment.machine.add_state(state.name, state)
        for transition in ctx.transition():
            tr = yield self.visit(transition)
            state.add_transition(tr[0], tr[1])
        state.add_activation_function(ctx.function())

    def visitTransition(self, ctx:LanguageParser.TransitionContext):
        yield ctx.ID(0).getText(), ctx.ID(1).getText()

    def visitFunction(self, ctx:LanguageParser.FunctionContext):
        yield self.visit(ctx.body())

    def visitVariable(self, ctx: LanguageParser.VariableContext):
        if not ctx.ID().getText() in self._environment.scopes[self._environment.sp]:
            raise Exception("Undefined variable: " + str(ctx.ID().getText()))
        yield self._environment.scopes[self._environment.sp][ctx.ID().getText()]

    def visitLiteral(self, ctx: LanguageParser.LiteralContext):
        if ctx.variable() is not None:
            yield self.visit(ctx.variable())
        elif ctx.STRING() is not None:
            yield ctx.STRING().getText()
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

    def visitCall(self, ctx: LanguageParser.CallContext):
        if not ctx.ID().getText() in self._environment.primitives:
            raise Exception("Undefined function: " + str(ctx.ID().getText()))

        # Get the function from the supported ones
        function = self._environment.primitives[ctx.ID().getText()]
        arguments = yield self.visit(ctx.arguments())

        # Execute the function
        function(*arguments)

    def visitHalt(self, ctx:LanguageParser.HaltContext):
        self.halt()

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

        if self._environment.machine.initial_state not in self._environment.machine.states:
            raise Exception("Initial state " + self._environment.machine.initial_state + " not defined")

        command = input("Enter an event " + str(self._environment.machine.events) + " or stop: ")
        self._environment.current_state = self._environment.machine.states[self._environment.machine.initial_state]
        while command != "stop":
            if command not in self._environment.machine.events:
                raise Exception("Unrecognized event: " + str(command))

            if not command in self._environment.current_state.transitions:
                raise Exception("Cannot execute transition event \"" + str(command) + "\" from current state: " + str(self._environment.current_state))

            target = self._environment.current_state.transitions[command]
            if not target in self._environment.machine.states:
                raise Exception("Cannot execute transition event " + str(command) + " from as " + target + " does not exist in the machine")

            self._environment.current_state = self._environment.machine.states[target]
            if self._environment.current_state.activation_function is not None:
                yield self.visit(self._environment.current_state.activation_function)

            command = input("Enter an event " + str(self._environment.machine.events) + " or stop: ")

del LanguageParser