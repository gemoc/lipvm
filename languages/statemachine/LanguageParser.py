# Generated from languages/statemachine/Language.g4 by ANTLR 4.13.2
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,21,147,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,2,12,7,12,2,13,7,13,
        2,14,7,14,2,15,7,15,1,0,1,0,1,0,1,1,1,1,5,1,38,8,1,10,1,12,1,41,
        9,1,1,2,1,2,1,2,1,3,1,3,1,3,5,3,49,8,3,10,3,12,3,52,9,3,1,3,3,3,
        55,8,3,1,3,1,3,1,4,1,4,1,4,1,4,1,5,1,5,1,5,1,6,1,6,1,7,1,7,1,7,3,
        7,71,8,7,1,8,1,8,1,8,1,8,1,8,1,8,3,8,79,8,8,1,8,1,8,1,8,5,8,84,8,
        8,10,8,12,8,87,9,8,1,9,1,9,1,9,5,9,92,8,9,10,9,12,9,95,9,9,1,10,
        1,10,1,10,3,10,100,8,10,1,10,1,10,1,11,1,11,1,11,1,11,1,12,1,12,
        1,12,1,12,1,12,5,12,113,8,12,10,12,12,12,116,9,12,1,12,1,12,1,13,
        1,13,1,13,1,13,1,14,1,14,1,14,1,14,1,14,1,14,1,14,1,14,1,14,1,14,
        1,14,1,14,3,14,136,8,14,1,15,1,15,1,15,1,15,5,15,142,8,15,10,15,
        12,15,145,9,15,1,15,0,1,16,16,0,2,4,6,8,10,12,14,16,18,20,22,24,
        26,28,30,0,0,145,0,32,1,0,0,0,2,35,1,0,0,0,4,42,1,0,0,0,6,45,1,0,
        0,0,8,58,1,0,0,0,10,62,1,0,0,0,12,65,1,0,0,0,14,70,1,0,0,0,16,78,
        1,0,0,0,18,88,1,0,0,0,20,96,1,0,0,0,22,103,1,0,0,0,24,107,1,0,0,
        0,26,119,1,0,0,0,28,135,1,0,0,0,30,137,1,0,0,0,32,33,5,1,0,0,33,
        34,5,13,0,0,34,1,1,0,0,0,35,39,5,2,0,0,36,38,5,13,0,0,37,36,1,0,
        0,0,38,41,1,0,0,0,39,37,1,0,0,0,39,40,1,0,0,0,40,3,1,0,0,0,41,39,
        1,0,0,0,42,43,5,3,0,0,43,44,5,13,0,0,44,5,1,0,0,0,45,46,5,4,0,0,
        46,50,5,13,0,0,47,49,3,8,4,0,48,47,1,0,0,0,49,52,1,0,0,0,50,48,1,
        0,0,0,50,51,1,0,0,0,51,54,1,0,0,0,52,50,1,0,0,0,53,55,3,10,5,0,54,
        53,1,0,0,0,54,55,1,0,0,0,55,56,1,0,0,0,56,57,5,5,0,0,57,7,1,0,0,
        0,58,59,5,13,0,0,59,60,5,6,0,0,60,61,5,13,0,0,61,9,1,0,0,0,62,63,
        5,7,0,0,63,64,3,24,12,0,64,11,1,0,0,0,65,66,5,13,0,0,66,13,1,0,0,
        0,67,71,3,12,6,0,68,71,5,14,0,0,69,71,5,15,0,0,70,67,1,0,0,0,70,
        68,1,0,0,0,70,69,1,0,0,0,71,15,1,0,0,0,72,73,6,8,-1,0,73,79,3,14,
        7,0,74,75,5,17,0,0,75,76,3,16,8,0,76,77,5,18,0,0,77,79,1,0,0,0,78,
        72,1,0,0,0,78,74,1,0,0,0,79,85,1,0,0,0,80,81,10,3,0,0,81,82,5,16,
        0,0,82,84,3,16,8,4,83,80,1,0,0,0,84,87,1,0,0,0,85,83,1,0,0,0,85,
        86,1,0,0,0,86,17,1,0,0,0,87,85,1,0,0,0,88,93,3,16,8,0,89,90,5,8,
        0,0,90,92,3,16,8,0,91,89,1,0,0,0,92,95,1,0,0,0,93,91,1,0,0,0,93,
        94,1,0,0,0,94,19,1,0,0,0,95,93,1,0,0,0,96,97,5,13,0,0,97,99,5,17,
        0,0,98,100,3,18,9,0,99,98,1,0,0,0,99,100,1,0,0,0,100,101,1,0,0,0,
        101,102,5,18,0,0,102,21,1,0,0,0,103,104,5,9,0,0,104,105,5,17,0,0,
        105,106,5,18,0,0,106,23,1,0,0,0,107,114,5,19,0,0,108,113,3,26,13,
        0,109,113,3,20,10,0,110,113,3,22,11,0,111,113,3,28,14,0,112,108,
        1,0,0,0,112,109,1,0,0,0,112,110,1,0,0,0,112,111,1,0,0,0,113,116,
        1,0,0,0,114,112,1,0,0,0,114,115,1,0,0,0,115,117,1,0,0,0,116,114,
        1,0,0,0,117,118,5,20,0,0,118,25,1,0,0,0,119,120,5,13,0,0,120,121,
        5,10,0,0,121,122,3,16,8,0,122,27,1,0,0,0,123,124,5,11,0,0,124,125,
        3,26,13,0,125,126,5,12,0,0,126,127,3,16,8,0,127,128,3,24,12,0,128,
        136,1,0,0,0,129,130,5,11,0,0,130,131,3,12,6,0,131,132,5,12,0,0,132,
        133,3,16,8,0,133,134,3,24,12,0,134,136,1,0,0,0,135,123,1,0,0,0,135,
        129,1,0,0,0,136,29,1,0,0,0,137,138,3,0,0,0,138,139,3,2,1,0,139,143,
        3,4,2,0,140,142,3,6,3,0,141,140,1,0,0,0,142,145,1,0,0,0,143,141,
        1,0,0,0,143,144,1,0,0,0,144,31,1,0,0,0,145,143,1,0,0,0,12,39,50,
        54,70,78,85,93,99,112,114,135,143
    ]

class LanguageParser ( Parser ):

    grammarFileName = "Language.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "'statemachine'", "'events'", "'initialState'", 
                     "'state'", "'end'", "'=>'", "'activate:'", "','", "'halt'", 
                     "'='", "'for'", "'to'", "<INVALID>", "<INVALID>", "<INVALID>", 
                     "<INVALID>", "'('", "')'", "'{'", "'}'" ]

    symbolicNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "ID", "NUMBER", "STRING", "OPERATOR", 
                      "LPAREN", "RPAREN", "LCBRACKET", "RCBRACKET", "WS" ]

    RULE_machine = 0
    RULE_events = 1
    RULE_initial = 2
    RULE_state = 3
    RULE_transition = 4
    RULE_function = 5
    RULE_variable = 6
    RULE_literal = 7
    RULE_expression = 8
    RULE_arguments = 9
    RULE_call = 10
    RULE_halt = 11
    RULE_body = 12
    RULE_assignment = 13
    RULE_forloop = 14
    RULE_main = 15

    ruleNames =  [ "machine", "events", "initial", "state", "transition", 
                   "function", "variable", "literal", "expression", "arguments", 
                   "call", "halt", "body", "assignment", "forloop", "main" ]

    EOF = Token.EOF
    T__0=1
    T__1=2
    T__2=3
    T__3=4
    T__4=5
    T__5=6
    T__6=7
    T__7=8
    T__8=9
    T__9=10
    T__10=11
    T__11=12
    ID=13
    NUMBER=14
    STRING=15
    OPERATOR=16
    LPAREN=17
    RPAREN=18
    LCBRACKET=19
    RCBRACKET=20
    WS=21

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class MachineContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.name = None # Token

        def ID(self):
            return self.getToken(LanguageParser.ID, 0)

        def getRuleIndex(self):
            return LanguageParser.RULE_machine

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitMachine" ):
                return visitor.visitMachine(self)
            else:
                return visitor.visitChildren(self)




    def machine(self):

        localctx = LanguageParser.MachineContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_machine)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 32
            self.match(LanguageParser.T__0)
            self.state = 33
            localctx.name = self.match(LanguageParser.ID)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class EventsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.name = None # Token

        def ID(self, i:int=None):
            if i is None:
                return self.getTokens(LanguageParser.ID)
            else:
                return self.getToken(LanguageParser.ID, i)

        def getRuleIndex(self):
            return LanguageParser.RULE_events

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitEvents" ):
                return visitor.visitEvents(self)
            else:
                return visitor.visitChildren(self)




    def events(self):

        localctx = LanguageParser.EventsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_events)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 35
            self.match(LanguageParser.T__1)
            self.state = 39
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==13:
                self.state = 36
                localctx.name = self.match(LanguageParser.ID)
                self.state = 41
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class InitialContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.name = None # Token

        def ID(self):
            return self.getToken(LanguageParser.ID, 0)

        def getRuleIndex(self):
            return LanguageParser.RULE_initial

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitInitial" ):
                return visitor.visitInitial(self)
            else:
                return visitor.visitChildren(self)




    def initial(self):

        localctx = LanguageParser.InitialContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_initial)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 42
            self.match(LanguageParser.T__2)
            self.state = 43
            localctx.name = self.match(LanguageParser.ID)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StateContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.name = None # Token
            self.transitions = None # TransitionContext
            self.activate = None # FunctionContext

        def ID(self):
            return self.getToken(LanguageParser.ID, 0)

        def transition(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.TransitionContext)
            else:
                return self.getTypedRuleContext(LanguageParser.TransitionContext,i)


        def function(self):
            return self.getTypedRuleContext(LanguageParser.FunctionContext,0)


        def getRuleIndex(self):
            return LanguageParser.RULE_state

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitState" ):
                return visitor.visitState(self)
            else:
                return visitor.visitChildren(self)




    def state_(self):

        localctx = LanguageParser.StateContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_state)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 45
            self.match(LanguageParser.T__3)
            self.state = 46
            localctx.name = self.match(LanguageParser.ID)
            self.state = 50
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==13:
                self.state = 47
                localctx.transitions = self.transition()
                self.state = 52
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 54
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==7:
                self.state = 53
                localctx.activate = self.function()


            self.state = 56
            self.match(LanguageParser.T__4)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TransitionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.name = None # Token
            self.stateName = None # Token

        def ID(self, i:int=None):
            if i is None:
                return self.getTokens(LanguageParser.ID)
            else:
                return self.getToken(LanguageParser.ID, i)

        def getRuleIndex(self):
            return LanguageParser.RULE_transition

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitTransition" ):
                return visitor.visitTransition(self)
            else:
                return visitor.visitChildren(self)




    def transition(self):

        localctx = LanguageParser.TransitionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_transition)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 58
            localctx.name = self.match(LanguageParser.ID)
            self.state = 59
            self.match(LanguageParser.T__5)
            self.state = 60
            localctx.stateName = self.match(LanguageParser.ID)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class FunctionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def body(self):
            return self.getTypedRuleContext(LanguageParser.BodyContext,0)


        def getRuleIndex(self):
            return LanguageParser.RULE_function

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitFunction" ):
                return visitor.visitFunction(self)
            else:
                return visitor.visitChildren(self)




    def function(self):

        localctx = LanguageParser.FunctionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_function)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 62
            self.match(LanguageParser.T__6)
            self.state = 63
            self.body()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class VariableContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.variableName = None # Token

        def ID(self):
            return self.getToken(LanguageParser.ID, 0)

        def getRuleIndex(self):
            return LanguageParser.RULE_variable

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitVariable" ):
                return visitor.visitVariable(self)
            else:
                return visitor.visitChildren(self)




    def variable(self):

        localctx = LanguageParser.VariableContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_variable)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 65
            localctx.variableName = self.match(LanguageParser.ID)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LiteralContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def variable(self):
            return self.getTypedRuleContext(LanguageParser.VariableContext,0)


        def NUMBER(self):
            return self.getToken(LanguageParser.NUMBER, 0)

        def STRING(self):
            return self.getToken(LanguageParser.STRING, 0)

        def getRuleIndex(self):
            return LanguageParser.RULE_literal

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLiteral" ):
                return visitor.visitLiteral(self)
            else:
                return visitor.visitChildren(self)




    def literal(self):

        localctx = LanguageParser.LiteralContext(self, self._ctx, self.state)
        self.enterRule(localctx, 14, self.RULE_literal)
        try:
            self.state = 70
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [13]:
                self.enterOuterAlt(localctx, 1)
                self.state = 67
                self.variable()
                pass
            elif token in [14]:
                self.enterOuterAlt(localctx, 2)
                self.state = 68
                self.match(LanguageParser.NUMBER)
                pass
            elif token in [15]:
                self.enterOuterAlt(localctx, 3)
                self.state = 69
                self.match(LanguageParser.STRING)
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.leftOperand = None # ExpressionContext
            self.op = None # Token
            self.rightOperand = None # ExpressionContext

        def literal(self):
            return self.getTypedRuleContext(LanguageParser.LiteralContext,0)


        def LPAREN(self):
            return self.getToken(LanguageParser.LPAREN, 0)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(LanguageParser.ExpressionContext,i)


        def RPAREN(self):
            return self.getToken(LanguageParser.RPAREN, 0)

        def OPERATOR(self):
            return self.getToken(LanguageParser.OPERATOR, 0)

        def getRuleIndex(self):
            return LanguageParser.RULE_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitExpression" ):
                return visitor.visitExpression(self)
            else:
                return visitor.visitChildren(self)



    def expression(self, _p:int=0):
        _parentctx = self._ctx
        _parentState = self.state
        localctx = LanguageParser.ExpressionContext(self, self._ctx, _parentState)
        _prevctx = localctx
        _startState = 16
        self.enterRecursionRule(localctx, 16, self.RULE_expression, _p)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 78
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [13, 14, 15]:
                self.state = 73
                self.literal()
                pass
            elif token in [17]:
                self.state = 74
                self.match(LanguageParser.LPAREN)
                self.state = 75
                self.expression(0)
                self.state = 76
                self.match(LanguageParser.RPAREN)
                pass
            else:
                raise NoViableAltException(self)

            self._ctx.stop = self._input.LT(-1)
            self.state = 85
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,5,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    if self._parseListeners is not None:
                        self.triggerExitRuleEvent()
                    _prevctx = localctx
                    localctx = LanguageParser.ExpressionContext(self, _parentctx, _parentState)
                    localctx.leftOperand = _prevctx
                    self.pushNewRecursionContext(localctx, _startState, self.RULE_expression)
                    self.state = 80
                    if not self.precpred(self._ctx, 3):
                        from antlr4.error.Errors import FailedPredicateException
                        raise FailedPredicateException(self, "self.precpred(self._ctx, 3)")
                    self.state = 81
                    localctx.op = self.match(LanguageParser.OPERATOR)
                    self.state = 82
                    localctx.rightOperand = self.expression(4) 
                self.state = 87
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,5,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.unrollRecursionContexts(_parentctx)
        return localctx


    class ArgumentsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(LanguageParser.ExpressionContext,i)


        def getRuleIndex(self):
            return LanguageParser.RULE_arguments

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitArguments" ):
                return visitor.visitArguments(self)
            else:
                return visitor.visitChildren(self)




    def arguments(self):

        localctx = LanguageParser.ArgumentsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 18, self.RULE_arguments)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 88
            self.expression(0)
            self.state = 93
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==8:
                self.state = 89
                self.match(LanguageParser.T__7)
                self.state = 90
                self.expression(0)
                self.state = 95
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class CallContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.functionName = None # Token
            self.args = None # ArgumentsContext

        def LPAREN(self):
            return self.getToken(LanguageParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(LanguageParser.RPAREN, 0)

        def ID(self):
            return self.getToken(LanguageParser.ID, 0)

        def arguments(self):
            return self.getTypedRuleContext(LanguageParser.ArgumentsContext,0)


        def getRuleIndex(self):
            return LanguageParser.RULE_call

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitCall" ):
                return visitor.visitCall(self)
            else:
                return visitor.visitChildren(self)




    def call(self):

        localctx = LanguageParser.CallContext(self, self._ctx, self.state)
        self.enterRule(localctx, 20, self.RULE_call)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 96
            localctx.functionName = self.match(LanguageParser.ID)
            self.state = 97
            self.match(LanguageParser.LPAREN)
            self.state = 99
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 188416) != 0):
                self.state = 98
                localctx.args = self.arguments()


            self.state = 101
            self.match(LanguageParser.RPAREN)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class HaltContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LPAREN(self):
            return self.getToken(LanguageParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(LanguageParser.RPAREN, 0)

        def getRuleIndex(self):
            return LanguageParser.RULE_halt

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitHalt" ):
                return visitor.visitHalt(self)
            else:
                return visitor.visitChildren(self)




    def halt(self):

        localctx = LanguageParser.HaltContext(self, self._ctx, self.state)
        self.enterRule(localctx, 22, self.RULE_halt)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 103
            self.match(LanguageParser.T__8)
            self.state = 104
            self.match(LanguageParser.LPAREN)
            self.state = 105
            self.match(LanguageParser.RPAREN)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class BodyContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LCBRACKET(self):
            return self.getToken(LanguageParser.LCBRACKET, 0)

        def RCBRACKET(self):
            return self.getToken(LanguageParser.RCBRACKET, 0)

        def assignment(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.AssignmentContext)
            else:
                return self.getTypedRuleContext(LanguageParser.AssignmentContext,i)


        def call(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.CallContext)
            else:
                return self.getTypedRuleContext(LanguageParser.CallContext,i)


        def halt(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.HaltContext)
            else:
                return self.getTypedRuleContext(LanguageParser.HaltContext,i)


        def forloop(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.ForloopContext)
            else:
                return self.getTypedRuleContext(LanguageParser.ForloopContext,i)


        def getRuleIndex(self):
            return LanguageParser.RULE_body

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBody" ):
                return visitor.visitBody(self)
            else:
                return visitor.visitChildren(self)




    def body(self):

        localctx = LanguageParser.BodyContext(self, self._ctx, self.state)
        self.enterRule(localctx, 24, self.RULE_body)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 107
            self.match(LanguageParser.LCBRACKET)
            self.state = 114
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 10752) != 0):
                self.state = 112
                self._errHandler.sync(self)
                la_ = self._interp.adaptivePredict(self._input,8,self._ctx)
                if la_ == 1:
                    self.state = 108
                    self.assignment()
                    pass

                elif la_ == 2:
                    self.state = 109
                    self.call()
                    pass

                elif la_ == 3:
                    self.state = 110
                    self.halt()
                    pass

                elif la_ == 4:
                    self.state = 111
                    self.forloop()
                    pass


                self.state = 116
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 117
            self.match(LanguageParser.RCBRACKET)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AssignmentContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.variableName = None # Token
            self.value = None # ExpressionContext

        def ID(self):
            return self.getToken(LanguageParser.ID, 0)

        def expression(self):
            return self.getTypedRuleContext(LanguageParser.ExpressionContext,0)


        def getRuleIndex(self):
            return LanguageParser.RULE_assignment

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAssignment" ):
                return visitor.visitAssignment(self)
            else:
                return visitor.visitChildren(self)




    def assignment(self):

        localctx = LanguageParser.AssignmentContext(self, self._ctx, self.state)
        self.enterRule(localctx, 26, self.RULE_assignment)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 119
            localctx.variableName = self.match(LanguageParser.ID)
            self.state = 120
            self.match(LanguageParser.T__9)
            self.state = 121
            localctx.value = self.expression(0)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ForloopContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.end = None # ExpressionContext

        def assignment(self):
            return self.getTypedRuleContext(LanguageParser.AssignmentContext,0)


        def body(self):
            return self.getTypedRuleContext(LanguageParser.BodyContext,0)


        def expression(self):
            return self.getTypedRuleContext(LanguageParser.ExpressionContext,0)


        def variable(self):
            return self.getTypedRuleContext(LanguageParser.VariableContext,0)


        def getRuleIndex(self):
            return LanguageParser.RULE_forloop

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitForloop" ):
                return visitor.visitForloop(self)
            else:
                return visitor.visitChildren(self)




    def forloop(self):

        localctx = LanguageParser.ForloopContext(self, self._ctx, self.state)
        self.enterRule(localctx, 28, self.RULE_forloop)
        try:
            self.state = 135
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,10,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 123
                self.match(LanguageParser.T__10)
                self.state = 124
                self.assignment()
                self.state = 125
                self.match(LanguageParser.T__11)
                self.state = 126
                localctx.end = self.expression(0)
                self.state = 127
                self.body()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 129
                self.match(LanguageParser.T__10)
                self.state = 130
                self.variable()
                self.state = 131
                self.match(LanguageParser.T__11)
                self.state = 132
                localctx.end = self.expression(0)
                self.state = 133
                self.body()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class MainContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def machine(self):
            return self.getTypedRuleContext(LanguageParser.MachineContext,0)


        def events(self):
            return self.getTypedRuleContext(LanguageParser.EventsContext,0)


        def initial(self):
            return self.getTypedRuleContext(LanguageParser.InitialContext,0)


        def state_(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.StateContext)
            else:
                return self.getTypedRuleContext(LanguageParser.StateContext,i)


        def getRuleIndex(self):
            return LanguageParser.RULE_main

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitMain" ):
                return visitor.visitMain(self)
            else:
                return visitor.visitChildren(self)




    def main(self):

        localctx = LanguageParser.MainContext(self, self._ctx, self.state)
        self.enterRule(localctx, 30, self.RULE_main)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 137
            self.machine()
            self.state = 138
            self.events()
            self.state = 139
            self.initial()
            self.state = 143
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==4:
                self.state = 140
                self.state_()
                self.state = 145
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx



    def sempred(self, localctx:RuleContext, ruleIndex:int, predIndex:int):
        if self._predicates == None:
            self._predicates = dict()
        self._predicates[8] = self.expression_sempred
        pred = self._predicates.get(ruleIndex, None)
        if pred is None:
            raise Exception("No predicate with index:" + str(ruleIndex))
        else:
            return pred(localctx, predIndex)

    def expression_sempred(self, localctx:ExpressionContext, predIndex:int):
            if predIndex == 0:
                return self.precpred(self._ctx, 3)
         




