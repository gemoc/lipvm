from unittest import TestCase
from time import sleep

from backend.lipvm import LipVM

class InterpreterTests(TestCase):

    def test_interpret(self):
        # Given
        vm = LipVM("languages.minilogo")

        code = "move(200,200)"
        code += "pen(down)"
        code += "move(300,200)"
        code += "pen(up)"

        # When
        vm.interpreter.interpret(code)

        # Then
        self.assertHasAttr(vm.interpreter.environment, "lines")
        self.assertEqual(1, len(vm.interpreter.environment.lines))
        self.assertEqual(vm.interpreter.environment.lines[0], ((200, 200), (300, 200) , "#FFFFFF"))

    def test_halt_proceed(self):
        # Given
        vm = LipVM("languages.minilogo")

        code = "move(200,200)"
        code += "pen(down)"
        code += "halt()"
        code += "move(300,200)"
        code += "pen(up)"

        # When
        vm.interpreter.interpret(code)

        # Then
        self.assertHasAttr(vm.interpreter.environment, "lines")
        self.assertEqual(0, len(vm.interpreter.environment.lines))

        # When
        vm.interpreter.proceed()

        # Then
        self.assertEqual(1, len(vm.interpreter.environment.lines))
        self.assertEqual(vm.interpreter.environment.lines[0], ((200, 200), (300, 200) , "#FFFFFF"))

    def test_halt_step_proceed(self):
        # Given
        vm = LipVM("languages.minilogo")

        code = "move(200,200)"
        code += "pen(down)"
        code += "halt()"
        code += "move(300,200)"
        code += "move(400,200)"
        code += "pen(up)"

        # When
        vm.interpreter.interpret(code)

        # Then
        self.assertHasAttr(vm.interpreter.environment, "lines")
        self.assertEqual(0, len(vm.interpreter.environment.lines))

        # When
        vm.interpreter.step()

        # Then
        self.assertEqual(1, len(vm.interpreter.environment.lines))
        self.assertEqual(vm.interpreter.environment.lines[0], ((200, 200), (300, 200), "#FFFFFF"))

        # When
        vm.interpreter.proceed()

        # Then
        self.assertEqual(2, len(vm.interpreter.environment.lines))
        self.assertEqual(vm.interpreter.environment.lines[1], ((300, 200), (400, 200), "#FFFFFF"))
