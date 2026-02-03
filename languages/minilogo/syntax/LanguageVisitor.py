# Generated from languages/Minilogo/syntax/Language.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .LanguageParser import LanguageParser
else:
    from LanguageParser import LanguageParser

# This class defines a complete generic visitor for a parse tree produced by LanguageParser.

class LanguageVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by LanguageParser#variable.
    def visitVariable(self, ctx:LanguageParser.VariableContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#literal.
    def visitLiteral(self, ctx:LanguageParser.LiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#expression.
    def visitExpression(self, ctx:LanguageParser.ExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#arguments.
    def visitArguments(self, ctx:LanguageParser.ArgumentsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#halt.
    def visitHalt(self, ctx:LanguageParser.HaltContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#move.
    def visitMove(self, ctx:LanguageParser.MoveContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#color.
    def visitColor(self, ctx:LanguageParser.ColorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#pen.
    def visitPen(self, ctx:LanguageParser.PenContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#call.
    def visitCall(self, ctx:LanguageParser.CallContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#def.
    def visitDef(self, ctx:LanguageParser.DefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#parameters.
    def visitParameters(self, ctx:LanguageParser.ParametersContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#body.
    def visitBody(self, ctx:LanguageParser.BodyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#assignment.
    def visitAssignment(self, ctx:LanguageParser.AssignmentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#forloop.
    def visitForloop(self, ctx:LanguageParser.ForloopContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#main.
    def visitMain(self, ctx:LanguageParser.MainContext):
        return self.visitChildren(ctx)



del LanguageParser