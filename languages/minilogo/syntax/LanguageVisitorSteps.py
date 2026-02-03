from antlr4 import *
from languages.minilogo.syntax.LanguageParser import LanguageParser

class LanguageVisitorSteps(ParseTreeVisitor):

    def visitVariable(self, ctx:LanguageParser.VariableContext):
        return self.visitChildren(ctx)

    def visitLiteral(self, ctx:LanguageParser.LiteralContext):
        return self.visitChildren(ctx)

    def visitExpression(self, ctx:LanguageParser.ExpressionContext):
        return self.visitChildren(ctx)

    def visitArguments(self, ctx:LanguageParser.ArgumentsContext):
        return self.visitChildren(ctx)

    def visitHalt(self, ctx:LanguageParser.HaltContext):
        return self.visitChildren(ctx)

    def visitMove(self, ctx:LanguageParser.MoveContext):
        ctx.stepNode = True
        return self.visitChildren(ctx)

    def visitColor(self, ctx:LanguageParser.ColorContext):
        return self.visitChildren(ctx)

    def visitPen(self, ctx:LanguageParser.PenContext):
        return self.visitChildren(ctx)

    def visitCall(self, ctx:LanguageParser.CallContext):
        return self.visitChildren(ctx)

    def visitDef(self, ctx:LanguageParser.DefContext):
        return self.visitChildren(ctx)

    def visitParameters(self, ctx:LanguageParser.ParametersContext):
        return self.visitChildren(ctx)

    def visitBody(self, ctx:LanguageParser.BodyContext):
        return self.visitChildren(ctx)

    def visitAssignment(self, ctx:LanguageParser.AssignmentContext):
        return self.visitChildren(ctx)

    def visitForloop(self, ctx:LanguageParser.ForloopContext):
        return self.visitChildren(ctx)

    def visitMain(self, ctx:LanguageParser.MainContext):
        return self.visitChildren(ctx)



del LanguageParser