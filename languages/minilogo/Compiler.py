import uuid

from antlr4 import *

# Language specific
from languages.minilogo.syntax import LanguageParser
from languages.minilogo.instructions.Addition import Addition
from languages.minilogo.instructions.Color import Color
from languages.minilogo.instructions.Division import Division
from languages.minilogo.instructions.EraseValueFromHeap import EraseValueFromHeap
from languages.minilogo.instructions.Increase import Increase
from languages.minilogo.instructions.Jump import Jump
from languages.minilogo.instructions.JumpIfEqual import JumpIfEqual
from languages.minilogo.instructions.LoadValue import LoadValue
from languages.minilogo.instructions.Move import Move
from languages.minilogo.instructions.Multiplication import Multiplication
from languages.minilogo.instructions.StartDrawing import StartDrawing
from languages.minilogo.instructions.StopDrawing import StopDrawing
from languages.minilogo.instructions.StoreValue import StoreValue
from languages.minilogo.instructions.Subtraction import Subtraction

# VM provided
from backend.Bytecode import Bytecode
from backend.Environment import Environment
from backend.instructions.Value import Value
from backend.instructions.SetLineNumber import SetLineNumber

class Compiler(ParseTreeVisitor):

    def __init__(self):
        super().__init__()
        self._last_emitted_line = -1  # Track last line number emitted

    def _emit_line_number(self, ctx):
        """Emit a SetLineNumber instruction if the line has changed"""
        if hasattr(ctx, 'start') and ctx.start is not None:
            line_num = ctx.start.line
            if line_num != self._last_emitted_line:
                self._bytecode.add(SetLineNumber(line_num))
                self._last_emitted_line = line_num

    # New implementation
    # Adding control flow, for loop
    def visitForAssign(self, ctx: LanguageParser.ForAssignContext):
        self._emit_line_number(ctx)

        # We only need random end loop identifier since the starting point exist already
        end_loop_identifier = uuid.uuid4().hex[:8]

        # Start loop comes from the local var assignment
        var_assignment_context = ctx.varAssignment()
        start_loop_identifier = ctx.varAssignment().identifier.text

        # Value of the loop end
        self.visit(ctx.end)

        # Identifier of the loop end
        self._bytecode.add(Value(end_loop_identifier))

        # Push instruction store value into the bytecode, to save the ending loop value
        self._bytecode.add(StoreValue())

        # Value of the loop start is coming from assignment
        # Resolve the var assignment and the starting point will be ready
        self.visit(var_assignment_context)

        # Mark the instruction point to jump, this is the starting point
        starting_point_ip = self._bytecode.size() - 1

        self._bytecode.add(Value(end_loop_identifier))
        self._bytecode.add(LoadValue())

        self._bytecode.add(Value(start_loop_identifier))
        self._bytecode.add(LoadValue())

        jump_to_end_instruction = JumpIfEqual()

        self._bytecode.add(jump_to_end_instruction)

        # Evaluate the block
        self.visit(ctx.block())

        # Add the starting pointer by one
        self._bytecode.add(Value(start_loop_identifier))
        self._bytecode.add(LoadValue())
        self._bytecode.add(Increase())
        self._bytecode.add(Value(start_loop_identifier))
        self._bytecode.add(StoreValue())

        # Jump to the loop starting point
        self._bytecode.add(Jump(starting_point_ip))

        # get the loop end and patch it with that value
        ending_point_ip = self._bytecode.size() - 1
        jump_to_end_instruction.loopend_ip = ending_point_ip

        # Clean the starting and ending loop pointer
        self._bytecode.add(EraseValueFromHeap([start_loop_identifier, end_loop_identifier]))

    def visitForVar(self, ctx: LanguageParser.ForVarContext):
        self._emit_line_number(ctx)

        start_loop_identifier = uuid.uuid4().hex[:8]
        end_loop_identifier = uuid.uuid4().hex[:8]

        # Value of the loop end
        self.visit(ctx.end)

        # Identifier of the loop end
        self._bytecode.add(Value(end_loop_identifier))

        # Push instruction store value into the bytecode, to save the ending loop value
        self._bytecode.add(StoreValue())

        # Value of the loop start
        self._bytecode.add(Value(ctx.varCall.text))
        self._bytecode.add(LoadValue())

        # Identifier of the loop start
        self._bytecode.add(Value(start_loop_identifier))

        # Push instruction store value into the bytecode, to save the starting loop value
        self._bytecode.add(StoreValue())

        # Mark the instruction point to jump, this is the starting point
        starting_point_ip = self._bytecode.size() - 1

        self._bytecode.add(Value(end_loop_identifier))
        self._bytecode.add(LoadValue())

        self._bytecode.add(Value(start_loop_identifier))
        self._bytecode.add(LoadValue())

        jump_to_end_instruction = JumpIfEqual()

        self._bytecode.add(jump_to_end_instruction)

        # Evaluate the block
        self.visit(ctx.block())

        # Add the starting pointer by one
        self._bytecode.add(Value(start_loop_identifier))
        self._bytecode.add(LoadValue())
        self._bytecode.add(Increase())
        self._bytecode.add(Value(start_loop_identifier))
        self._bytecode.add(StoreValue())

        # Jump to the loop starting point
        self._bytecode.add(Jump(starting_point_ip))

        # get the loop end and patch it with that value
        ending_point_ip = self._bytecode.size() - 1
        jump_to_end_instruction.loopend_ip = ending_point_ip

        # Clean the starting and ending loop pointer
        self._bytecode.add(EraseValueFromHeap([start_loop_identifier, end_loop_identifier]))

    def visitBlock(self, ctx: LanguageParser.BlockContext):

        list_of_commands = ctx.subcommands

        for command in list_of_commands:
            self.visit(command)

    def visitVarAssignment(self, ctx: LanguageParser.VarAssignmentContext):
        self._emit_line_number(ctx)

        # Evaluate value candidate
        self.visit(ctx.expression())

        # Push variable name value into the bytecode
        self._bytecode.add(Value(ctx.identifier.text))

        # Push instruction store value into the bytecode
        self._bytecode.add(StoreValue())

    def visitMove(self, ctx: LanguageParser.MoveContext):
        self._emit_line_number(ctx)

        # In original implementation, movement is only represented by integers
        # Now, it uses an expression that might be a result from arithmetic operation with integers or
        # value of a particular variable

        self.visit(ctx.x)
        self.visit(ctx.y)
        self._bytecode.add(Move())

    def visitExpression(self, ctx: LanguageParser.ExpressionContext):

        # Left is a term. So, resolve that
        self.visit(ctx.leftVal)

        if ctx.rightVal is not None:
            # Right is a term. So, resolve that
            self.visit(ctx.rightVal)

            operand = ctx.op.text

            if operand == '+':
                # Push the instruction to perform addition
                self._bytecode.add(Addition())
            elif operand == '-':
                # Push the instruction to perform substraction
                self._bytecode.add(Subtraction())

    def visitTerm(self, ctx: LanguageParser.TermContext):

        # Left is a factor. So, resolve that
        self.visit(ctx.leftVal)

        if ctx.rightVal is not None:
            # Right is a factor. So, resolve that
            self.visit(ctx.rightVal)

            operand = ctx.op.text

            if operand == '*':
                # Push the instruction to perform addition
                self._bytecode.add(Multiplication())
            elif operand == '/':
                # Push the instruction to perform substraction
                self._bytecode.add(Division())

    def visitFactor(self, ctx: LanguageParser.FactorContext):

        if ctx.ID() is not None:

            self._bytecode.add(Value(ctx.ID().getText()))
            self._bytecode.add(LoadValue())

        elif ctx.NUMBER() is not None:

            int_val = int(ctx.NUMBER().getText())
            self._bytecode.add(Value(int_val))

        else:

            self.visit(ctx.expression())

    def visitColor(self, ctx: LanguageParser.ColorContext):
        self._emit_line_number(ctx)
        self._bytecode.add(Value(ctx.code.text))
        self._bytecode.add(Color())

    def visitDraw(self, ctx: LanguageParser.DrawContext):
        self._emit_line_number(ctx)
        self._bytecode.add(StartDrawing())
        self.visitChildren(ctx)
        self._bytecode.add(StopDrawing())

    def visitStart(self, ctx: LanguageParser.StartContext):
        self.visitChildren(ctx)

    def compile(self, ast):
        self._bytecode = Bytecode()
        self.visit(ast)
        return self._bytecode