# Generated from languages/minilogo/Language.g4 by ANTLR 4.13.2
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
        4,1,22,153,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,2,12,7,12,2,13,7,13,
        2,14,7,14,1,0,1,0,1,1,1,1,1,2,1,2,1,2,1,2,1,2,1,2,1,2,3,2,42,8,2,
        1,2,1,2,1,2,5,2,47,8,2,10,2,12,2,50,9,2,1,3,1,3,1,3,5,3,55,8,3,10,
        3,12,3,58,9,3,1,4,1,4,1,4,1,4,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,6,1,
        6,1,6,1,6,1,6,1,7,1,7,1,7,1,7,1,7,1,8,1,8,1,8,3,8,84,8,8,1,8,1,8,
        1,9,1,9,1,9,1,9,3,9,92,8,9,1,9,1,9,1,9,1,10,1,10,1,10,5,10,100,8,
        10,10,10,12,10,103,9,10,1,11,1,11,1,11,1,11,1,11,1,11,1,11,1,11,
        1,11,5,11,114,8,11,10,11,12,11,117,9,11,1,11,1,11,1,12,1,12,1,12,
        1,12,1,13,1,13,1,13,1,13,1,13,1,13,1,13,1,13,1,13,1,13,1,13,1,13,
        3,13,137,8,13,1,14,1,14,1,14,1,14,1,14,1,14,1,14,1,14,1,14,5,14,
        148,8,14,10,14,12,14,151,9,14,1,14,0,1,4,15,0,2,4,6,8,10,12,14,16,
        18,20,22,24,26,28,0,1,1,0,6,7,162,0,30,1,0,0,0,2,32,1,0,0,0,4,41,
        1,0,0,0,6,51,1,0,0,0,8,59,1,0,0,0,10,63,1,0,0,0,12,70,1,0,0,0,14,
        75,1,0,0,0,16,80,1,0,0,0,18,87,1,0,0,0,20,96,1,0,0,0,22,104,1,0,
        0,0,24,120,1,0,0,0,26,136,1,0,0,0,28,149,1,0,0,0,30,31,5,12,0,0,
        31,1,1,0,0,0,32,33,5,13,0,0,33,3,1,0,0,0,34,35,6,2,-1,0,35,42,3,
        0,0,0,36,42,3,2,1,0,37,38,5,15,0,0,38,39,3,4,2,0,39,40,5,16,0,0,
        40,42,1,0,0,0,41,34,1,0,0,0,41,36,1,0,0,0,41,37,1,0,0,0,42,48,1,
        0,0,0,43,44,10,4,0,0,44,45,5,14,0,0,45,47,3,4,2,5,46,43,1,0,0,0,
        47,50,1,0,0,0,48,46,1,0,0,0,48,49,1,0,0,0,49,5,1,0,0,0,50,48,1,0,
        0,0,51,56,3,4,2,0,52,53,5,1,0,0,53,55,3,4,2,0,54,52,1,0,0,0,55,58,
        1,0,0,0,56,54,1,0,0,0,56,57,1,0,0,0,57,7,1,0,0,0,58,56,1,0,0,0,59,
        60,5,2,0,0,60,61,5,15,0,0,61,62,5,16,0,0,62,9,1,0,0,0,63,64,5,3,
        0,0,64,65,5,15,0,0,65,66,3,4,2,0,66,67,5,1,0,0,67,68,3,4,2,0,68,
        69,5,16,0,0,69,11,1,0,0,0,70,71,5,4,0,0,71,72,5,15,0,0,72,73,5,20,
        0,0,73,74,5,16,0,0,74,13,1,0,0,0,75,76,5,5,0,0,76,77,5,15,0,0,77,
        78,7,0,0,0,78,79,5,16,0,0,79,15,1,0,0,0,80,81,5,12,0,0,81,83,5,15,
        0,0,82,84,3,6,3,0,83,82,1,0,0,0,83,84,1,0,0,0,84,85,1,0,0,0,85,86,
        5,16,0,0,86,17,1,0,0,0,87,88,5,8,0,0,88,89,5,12,0,0,89,91,5,15,0,
        0,90,92,3,20,10,0,91,90,1,0,0,0,91,92,1,0,0,0,92,93,1,0,0,0,93,94,
        5,16,0,0,94,95,3,22,11,0,95,19,1,0,0,0,96,101,5,12,0,0,97,98,5,1,
        0,0,98,100,5,12,0,0,99,97,1,0,0,0,100,103,1,0,0,0,101,99,1,0,0,0,
        101,102,1,0,0,0,102,21,1,0,0,0,103,101,1,0,0,0,104,115,5,17,0,0,
        105,114,3,24,12,0,106,114,3,16,8,0,107,114,3,10,5,0,108,114,3,12,
        6,0,109,114,3,14,7,0,110,114,3,8,4,0,111,114,3,26,13,0,112,114,5,
        22,0,0,113,105,1,0,0,0,113,106,1,0,0,0,113,107,1,0,0,0,113,108,1,
        0,0,0,113,109,1,0,0,0,113,110,1,0,0,0,113,111,1,0,0,0,113,112,1,
        0,0,0,114,117,1,0,0,0,115,113,1,0,0,0,115,116,1,0,0,0,116,118,1,
        0,0,0,117,115,1,0,0,0,118,119,5,18,0,0,119,23,1,0,0,0,120,121,5,
        12,0,0,121,122,5,9,0,0,122,123,3,4,2,0,123,25,1,0,0,0,124,125,5,
        10,0,0,125,126,3,24,12,0,126,127,5,11,0,0,127,128,3,4,2,0,128,129,
        3,22,11,0,129,137,1,0,0,0,130,131,5,10,0,0,131,132,3,0,0,0,132,133,
        5,11,0,0,133,134,3,4,2,0,134,135,3,22,11,0,135,137,1,0,0,0,136,124,
        1,0,0,0,136,130,1,0,0,0,137,27,1,0,0,0,138,148,3,24,12,0,139,148,
        3,18,9,0,140,148,3,16,8,0,141,148,3,10,5,0,142,148,3,12,6,0,143,
        148,3,14,7,0,144,148,3,8,4,0,145,148,3,26,13,0,146,148,5,22,0,0,
        147,138,1,0,0,0,147,139,1,0,0,0,147,140,1,0,0,0,147,141,1,0,0,0,
        147,142,1,0,0,0,147,143,1,0,0,0,147,144,1,0,0,0,147,145,1,0,0,0,
        147,146,1,0,0,0,148,151,1,0,0,0,149,147,1,0,0,0,149,150,1,0,0,0,
        150,29,1,0,0,0,151,149,1,0,0,0,11,41,48,56,83,91,101,113,115,136,
        147,149
    ]

class LanguageParser ( Parser ):

    grammarFileName = "Language.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "','", "'halt'", "'move'", "'color'", 
                     "'pen'", "'up'", "'down'", "'def'", "'='", "'for'", 
                     "'to'", "<INVALID>", "<INVALID>", "<INVALID>", "'('", 
                     "')'", "'{'", "'}'" ]

    symbolicNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "ID", "NUMBER", "OPERATOR", "LPAREN", "RPAREN", "LCBRACKET", 
                      "RCBRACKET", "HEX", "COLOR", "WS", "COMMENT" ]

    RULE_variable = 0
    RULE_literal = 1
    RULE_expression = 2
    RULE_arguments = 3
    RULE_halt = 4
    RULE_move = 5
    RULE_color = 6
    RULE_pen = 7
    RULE_call = 8
    RULE_def = 9
    RULE_parameters = 10
    RULE_body = 11
    RULE_assignment = 12
    RULE_forloop = 13
    RULE_main = 14

    ruleNames =  [ "variable", "literal", "expression", "arguments", "halt", 
                   "move", "color", "pen", "call", "def", "parameters", 
                   "body", "assignment", "forloop", "main" ]

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
    ID=12
    NUMBER=13
    OPERATOR=14
    LPAREN=15
    RPAREN=16
    LCBRACKET=17
    RCBRACKET=18
    HEX=19
    COLOR=20
    WS=21
    COMMENT=22

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




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
        self.enterRule(localctx, 0, self.RULE_variable)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 30
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

        def NUMBER(self):
            return self.getToken(LanguageParser.NUMBER, 0)

        def getRuleIndex(self):
            return LanguageParser.RULE_literal

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLiteral" ):
                return visitor.visitLiteral(self)
            else:
                return visitor.visitChildren(self)




    def literal(self):

        localctx = LanguageParser.LiteralContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_literal)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 32
            self.match(LanguageParser.NUMBER)
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

        def variable(self):
            return self.getTypedRuleContext(LanguageParser.VariableContext,0)


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
        _startState = 4
        self.enterRecursionRule(localctx, 4, self.RULE_expression, _p)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 41
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [12]:
                self.state = 35
                self.variable()
                pass
            elif token in [13]:
                self.state = 36
                self.literal()
                pass
            elif token in [15]:
                self.state = 37
                self.match(LanguageParser.LPAREN)
                self.state = 38
                self.expression(0)
                self.state = 39
                self.match(LanguageParser.RPAREN)
                pass
            else:
                raise NoViableAltException(self)

            self._ctx.stop = self._input.LT(-1)
            self.state = 48
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,1,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    if self._parseListeners is not None:
                        self.triggerExitRuleEvent()
                    _prevctx = localctx
                    localctx = LanguageParser.ExpressionContext(self, _parentctx, _parentState)
                    localctx.leftOperand = _prevctx
                    self.pushNewRecursionContext(localctx, _startState, self.RULE_expression)
                    self.state = 43
                    if not self.precpred(self._ctx, 4):
                        from antlr4.error.Errors import FailedPredicateException
                        raise FailedPredicateException(self, "self.precpred(self._ctx, 4)")
                    self.state = 44
                    localctx.op = self.match(LanguageParser.OPERATOR)
                    self.state = 45
                    localctx.rightOperand = self.expression(5) 
                self.state = 50
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,1,self._ctx)

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
        self.enterRule(localctx, 6, self.RULE_arguments)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 51
            self.expression(0)
            self.state = 56
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==1:
                self.state = 52
                self.match(LanguageParser.T__0)
                self.state = 53
                self.expression(0)
                self.state = 58
                self._errHandler.sync(self)
                _la = self._input.LA(1)

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
        self.enterRule(localctx, 8, self.RULE_halt)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 59
            self.match(LanguageParser.T__1)
            self.state = 60
            self.match(LanguageParser.LPAREN)
            self.state = 61
            self.match(LanguageParser.RPAREN)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class MoveContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.x = None # ExpressionContext
            self.y = None # ExpressionContext

        def LPAREN(self):
            return self.getToken(LanguageParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(LanguageParser.RPAREN, 0)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(LanguageParser.ExpressionContext,i)


        def getRuleIndex(self):
            return LanguageParser.RULE_move

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitMove" ):
                return visitor.visitMove(self)
            else:
                return visitor.visitChildren(self)




    def move(self):

        localctx = LanguageParser.MoveContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_move)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 63
            self.match(LanguageParser.T__2)
            self.state = 64
            self.match(LanguageParser.LPAREN)
            self.state = 65
            localctx.x = self.expression(0)
            self.state = 66
            self.match(LanguageParser.T__0)
            self.state = 67
            localctx.y = self.expression(0)
            self.state = 68
            self.match(LanguageParser.RPAREN)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ColorContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.code = None # Token

        def LPAREN(self):
            return self.getToken(LanguageParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(LanguageParser.RPAREN, 0)

        def COLOR(self):
            return self.getToken(LanguageParser.COLOR, 0)

        def getRuleIndex(self):
            return LanguageParser.RULE_color

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitColor" ):
                return visitor.visitColor(self)
            else:
                return visitor.visitChildren(self)




    def color(self):

        localctx = LanguageParser.ColorContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_color)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 70
            self.match(LanguageParser.T__3)
            self.state = 71
            self.match(LanguageParser.LPAREN)
            self.state = 72
            localctx.code = self.match(LanguageParser.COLOR)
            self.state = 73
            self.match(LanguageParser.RPAREN)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PenContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.status = None # Token

        def LPAREN(self):
            return self.getToken(LanguageParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(LanguageParser.RPAREN, 0)

        def getRuleIndex(self):
            return LanguageParser.RULE_pen

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPen" ):
                return visitor.visitPen(self)
            else:
                return visitor.visitChildren(self)




    def pen(self):

        localctx = LanguageParser.PenContext(self, self._ctx, self.state)
        self.enterRule(localctx, 14, self.RULE_pen)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 75
            self.match(LanguageParser.T__4)
            self.state = 76
            self.match(LanguageParser.LPAREN)
            self.state = 77
            localctx.status = self._input.LT(1)
            _la = self._input.LA(1)
            if not(_la==6 or _la==7):
                localctx.status = self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
            self.state = 78
            self.match(LanguageParser.RPAREN)
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
        self.enterRule(localctx, 16, self.RULE_call)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 80
            localctx.functionName = self.match(LanguageParser.ID)
            self.state = 81
            self.match(LanguageParser.LPAREN)
            self.state = 83
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 45056) != 0):
                self.state = 82
                localctx.args = self.arguments()


            self.state = 85
            self.match(LanguageParser.RPAREN)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class DefContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.functionName = None # Token
            self.params = None # ParametersContext

        def LPAREN(self):
            return self.getToken(LanguageParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(LanguageParser.RPAREN, 0)

        def body(self):
            return self.getTypedRuleContext(LanguageParser.BodyContext,0)


        def ID(self):
            return self.getToken(LanguageParser.ID, 0)

        def parameters(self):
            return self.getTypedRuleContext(LanguageParser.ParametersContext,0)


        def getRuleIndex(self):
            return LanguageParser.RULE_def

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitDef" ):
                return visitor.visitDef(self)
            else:
                return visitor.visitChildren(self)




    def def_(self):

        localctx = LanguageParser.DefContext(self, self._ctx, self.state)
        self.enterRule(localctx, 18, self.RULE_def)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 87
            self.match(LanguageParser.T__7)
            self.state = 88
            localctx.functionName = self.match(LanguageParser.ID)
            self.state = 89
            self.match(LanguageParser.LPAREN)
            self.state = 91
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==12:
                self.state = 90
                localctx.params = self.parameters()


            self.state = 93
            self.match(LanguageParser.RPAREN)
            self.state = 94
            self.body()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ParametersContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.variableName = None # Token

        def ID(self, i:int=None):
            if i is None:
                return self.getTokens(LanguageParser.ID)
            else:
                return self.getToken(LanguageParser.ID, i)

        def getRuleIndex(self):
            return LanguageParser.RULE_parameters

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitParameters" ):
                return visitor.visitParameters(self)
            else:
                return visitor.visitChildren(self)




    def parameters(self):

        localctx = LanguageParser.ParametersContext(self, self._ctx, self.state)
        self.enterRule(localctx, 20, self.RULE_parameters)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 96
            localctx.variableName = self.match(LanguageParser.ID)
            self.state = 101
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==1:
                self.state = 97
                self.match(LanguageParser.T__0)
                self.state = 98
                localctx.variableName = self.match(LanguageParser.ID)
                self.state = 103
                self._errHandler.sync(self)
                _la = self._input.LA(1)

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


        def move(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.MoveContext)
            else:
                return self.getTypedRuleContext(LanguageParser.MoveContext,i)


        def color(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.ColorContext)
            else:
                return self.getTypedRuleContext(LanguageParser.ColorContext,i)


        def pen(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.PenContext)
            else:
                return self.getTypedRuleContext(LanguageParser.PenContext,i)


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


        def COMMENT(self, i:int=None):
            if i is None:
                return self.getTokens(LanguageParser.COMMENT)
            else:
                return self.getToken(LanguageParser.COMMENT, i)

        def getRuleIndex(self):
            return LanguageParser.RULE_body

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBody" ):
                return visitor.visitBody(self)
            else:
                return visitor.visitChildren(self)




    def body(self):

        localctx = LanguageParser.BodyContext(self, self._ctx, self.state)
        self.enterRule(localctx, 22, self.RULE_body)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 104
            self.match(LanguageParser.LCBRACKET)
            self.state = 115
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 4199484) != 0):
                self.state = 113
                self._errHandler.sync(self)
                la_ = self._interp.adaptivePredict(self._input,6,self._ctx)
                if la_ == 1:
                    self.state = 105
                    self.assignment()
                    pass

                elif la_ == 2:
                    self.state = 106
                    self.call()
                    pass

                elif la_ == 3:
                    self.state = 107
                    self.move()
                    pass

                elif la_ == 4:
                    self.state = 108
                    self.color()
                    pass

                elif la_ == 5:
                    self.state = 109
                    self.pen()
                    pass

                elif la_ == 6:
                    self.state = 110
                    self.halt()
                    pass

                elif la_ == 7:
                    self.state = 111
                    self.forloop()
                    pass

                elif la_ == 8:
                    self.state = 112
                    self.match(LanguageParser.COMMENT)
                    pass


                self.state = 117
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 118
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
        self.enterRule(localctx, 24, self.RULE_assignment)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 120
            localctx.variableName = self.match(LanguageParser.ID)
            self.state = 121
            self.match(LanguageParser.T__8)
            self.state = 122
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
        self.enterRule(localctx, 26, self.RULE_forloop)
        try:
            self.state = 136
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,8,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 124
                self.match(LanguageParser.T__9)
                self.state = 125
                self.assignment()
                self.state = 126
                self.match(LanguageParser.T__10)
                self.state = 127
                localctx.end = self.expression(0)
                self.state = 128
                self.body()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 130
                self.match(LanguageParser.T__9)
                self.state = 131
                self.variable()
                self.state = 132
                self.match(LanguageParser.T__10)
                self.state = 133
                localctx.end = self.expression(0)
                self.state = 134
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

        def assignment(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.AssignmentContext)
            else:
                return self.getTypedRuleContext(LanguageParser.AssignmentContext,i)


        def def_(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.DefContext)
            else:
                return self.getTypedRuleContext(LanguageParser.DefContext,i)


        def call(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.CallContext)
            else:
                return self.getTypedRuleContext(LanguageParser.CallContext,i)


        def move(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.MoveContext)
            else:
                return self.getTypedRuleContext(LanguageParser.MoveContext,i)


        def color(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.ColorContext)
            else:
                return self.getTypedRuleContext(LanguageParser.ColorContext,i)


        def pen(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(LanguageParser.PenContext)
            else:
                return self.getTypedRuleContext(LanguageParser.PenContext,i)


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


        def COMMENT(self, i:int=None):
            if i is None:
                return self.getTokens(LanguageParser.COMMENT)
            else:
                return self.getToken(LanguageParser.COMMENT, i)

        def getRuleIndex(self):
            return LanguageParser.RULE_main

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitMain" ):
                return visitor.visitMain(self)
            else:
                return visitor.visitChildren(self)




    def main(self):

        localctx = LanguageParser.MainContext(self, self._ctx, self.state)
        self.enterRule(localctx, 28, self.RULE_main)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 149
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 4199740) != 0):
                self.state = 147
                self._errHandler.sync(self)
                la_ = self._interp.adaptivePredict(self._input,9,self._ctx)
                if la_ == 1:
                    self.state = 138
                    self.assignment()
                    pass

                elif la_ == 2:
                    self.state = 139
                    self.def_()
                    pass

                elif la_ == 3:
                    self.state = 140
                    self.call()
                    pass

                elif la_ == 4:
                    self.state = 141
                    self.move()
                    pass

                elif la_ == 5:
                    self.state = 142
                    self.color()
                    pass

                elif la_ == 6:
                    self.state = 143
                    self.pen()
                    pass

                elif la_ == 7:
                    self.state = 144
                    self.halt()
                    pass

                elif la_ == 8:
                    self.state = 145
                    self.forloop()
                    pass

                elif la_ == 9:
                    self.state = 146
                    self.match(LanguageParser.COMMENT)
                    pass


                self.state = 151
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
        self._predicates[2] = self.expression_sempred
        pred = self._predicates.get(ruleIndex, None)
        if pred is None:
            raise Exception("No predicate with index:" + str(ruleIndex))
        else:
            return pred(localctx, predIndex)

    def expression_sempred(self, localctx:ExpressionContext, predIndex:int):
            if predIndex == 0:
                return self.precpred(self._ctx, 4)
         




