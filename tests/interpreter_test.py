from backend.lipvm import LipVM

def test_interpret():
    # Given
    vm = LipVM("languages.minilogo")

    code = "move(200,200)"
    code += "pen(down)"
    code += "move(300,200)"
    code += "pen(up)"

    # When
    vm.interpreter.interpret(code)

    # Then
    assert hasattr(vm.interpreter.environment, "lines")
    assert len(vm.interpreter.environment.lines) == 1
    assert vm.interpreter.environment.lines[0] == ((200, 200), (300, 200) , "#FFFFFF")

def test_halt_proceed():
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
    assert hasattr(vm.interpreter.environment, "lines")
    assert len(vm.interpreter.environment.lines) == 0

    # When
    vm.interpreter.proceed()

    # Then
    assert len(vm.interpreter.environment.lines) == 1
    assert vm.interpreter.environment.lines[0] == ((200, 200), (300, 200) , "#FFFFFF")

def test_halt_step_proceed():
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
    assert hasattr(vm.interpreter.environment, "lines")
    assert len(vm.interpreter.environment.lines) == 0

    # When
    vm.interpreter.step() # Move to the beginning of next step
    vm.interpreter.step() # Move to the end of next step

    # Then
    assert len(vm.interpreter.environment.lines) == 1
    assert vm.interpreter.environment.lines[0] == ((200, 200), (300, 200), "#FFFFFF")

    # When
    vm.interpreter.proceed()

    # Then
    assert len(vm.interpreter.environment.lines) == 2
    assert vm.interpreter.environment.lines[1] == ((300, 200), (400, 200), "#FFFFFF")
