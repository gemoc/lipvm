# Generated from languages/sysml/Language.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .LanguageParser import LanguageParser
else:
    from LanguageParser import LanguageParser

# This class defines a complete generic visitor for a parse tree produced by LanguageParser.

class LanguageVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by LanguageParser#main.
    def visitMain(self, ctx:LanguageParser.MainContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#model.
    def visitModel(self, ctx:LanguageParser.ModelContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#element.
    def visitElement(self, ctx:LanguageParser.ElementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#namespace.
    def visitNamespace(self, ctx:LanguageParser.NamespaceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#sysml2_package.
    def visitSysml2_package(self, ctx:LanguageParser.Sysml2_packageContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#part_blk.
    def visitPart_blk(self, ctx:LanguageParser.Part_blkContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#part.
    def visitPart(self, ctx:LanguageParser.PartContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#part_def.
    def visitPart_def(self, ctx:LanguageParser.Part_defContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#part_def_specializes.
    def visitPart_def_specializes(self, ctx:LanguageParser.Part_def_specializesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#port.
    def visitPort(self, ctx:LanguageParser.PortContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#port_def.
    def visitPort_def(self, ctx:LanguageParser.Port_defContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#port_blk.
    def visitPort_blk(self, ctx:LanguageParser.Port_blkContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#use_case_blk.
    def visitUse_case_blk(self, ctx:LanguageParser.Use_case_blkContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#use_case_def.
    def visitUse_case_def(self, ctx:LanguageParser.Use_case_defContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#part_objective_blk.
    def visitPart_objective_blk(self, ctx:LanguageParser.Part_objective_blkContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#objective_def.
    def visitObjective_def(self, ctx:LanguageParser.Objective_defContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#subject_def.
    def visitSubject_def(self, ctx:LanguageParser.Subject_defContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#include.
    def visitInclude(self, ctx:LanguageParser.IncludeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#include_blk.
    def visitInclude_blk(self, ctx:LanguageParser.Include_blkContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#message.
    def visitMessage(self, ctx:LanguageParser.MessageContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#message_expr.
    def visitMessage_expr(self, ctx:LanguageParser.Message_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#feature.
    def visitFeature(self, ctx:LanguageParser.FeatureContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#connection.
    def visitConnection(self, ctx:LanguageParser.ConnectionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#connection_blk.
    def visitConnection_blk(self, ctx:LanguageParser.Connection_blkContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#end_part.
    def visitEnd_part(self, ctx:LanguageParser.End_partContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#connect.
    def visitConnect(self, ctx:LanguageParser.ConnectContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#connect_expr.
    def visitConnect_expr(self, ctx:LanguageParser.Connect_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#feature_attribute_def.
    def visitFeature_attribute_def(self, ctx:LanguageParser.Feature_attribute_defContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#feature_attribute_redefines.
    def visitFeature_attribute_redefines(self, ctx:LanguageParser.Feature_attribute_redefinesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#feature_part_specializes.
    def visitFeature_part_specializes(self, ctx:LanguageParser.Feature_part_specializesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#feature_part_specializes_subsets.
    def visitFeature_part_specializes_subsets(self, ctx:LanguageParser.Feature_part_specializes_subsetsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#feature_item_def.
    def visitFeature_item_def(self, ctx:LanguageParser.Feature_item_defContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#feature_item_ref.
    def visitFeature_item_ref(self, ctx:LanguageParser.Feature_item_refContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#feature_actor_specializes.
    def visitFeature_actor_specializes(self, ctx:LanguageParser.Feature_actor_specializesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#comment.
    def visitComment(self, ctx:LanguageParser.CommentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#comment_unnamed.
    def visitComment_unnamed(self, ctx:LanguageParser.Comment_unnamedContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#comment_named.
    def visitComment_named(self, ctx:LanguageParser.Comment_namedContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#comment_named_about.
    def visitComment_named_about(self, ctx:LanguageParser.Comment_named_aboutContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#doc.
    def visitDoc(self, ctx:LanguageParser.DocContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#doc_unnamed.
    def visitDoc_unnamed(self, ctx:LanguageParser.Doc_unnamedContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#doc_named.
    def visitDoc_named(self, ctx:LanguageParser.Doc_namedContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#statement.
    def visitStatement(self, ctx:LanguageParser.StatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#import_package.
    def visitImport_package(self, ctx:LanguageParser.Import_packageContext):
        return self.visitChildren(ctx)



del LanguageParser