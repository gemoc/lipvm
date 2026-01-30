from backend.instructions.AbstractInstruction import AbstractInstruction

class SetLineNumber(AbstractInstruction):
    """Instruction to update the current line number in the environment"""
    
    def __init__(self, line_number):
        self.line_number = line_number
    
    def __str__(self):
        return f'SetLineNumber({self.line_number})'
    
    def need_to_have_snapshot(self):
        return False
    
    def execute(self, environment):
        environment.current_line = self.line_number
