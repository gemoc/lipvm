# LipVM

LipVM is a prototype of a generic virtual machine for executing DSLs (Domain
Specific Languages) programs, that are modeled with
[pyecore](https://github.com/pyecore/pyecore) (an EMF/Ecore implementation in
Python).

Instead of compiling a language to some bytecode, each language is described as
an **Ecore metamodel** (abstract syntax + runtime state) whose classes know how
to **evaluate themselves**.  
The VM turns this evaluation into a chain of resumable `Operation`s, which makes
it possible to:

- step through a program operation by operation,
- pause/resume execution,
- and apply **edit scripts** to the running abstract syntax tree to hot-swap or
  part of a program while it executes (live programming).

Two example languages are currently implemented:
- **Minilogo** (partially-implemented, functions and loops are missing): a
  graphics language that commands a pen to move accross a canvas coordinates.
- **Robot** : a maze-navigation language that commands a robot to turn a step
  through a maze path.

## Roadmap 

- [x] Test safepoint declaration. (in-progress)
- [x] Add the mecanism to prepare and declare a migration after a code change.
  (in-progress)
- [ ] Add the probing mecanism and expose it through LESP. (in-progress)
- [ ] Add connectors for RPC calls from Java (LESP?)

## Project structure

```
core/              Generic, language-independent VM machinery
  language.py      Base metamodel: AbstractSyntaxElement, RuntimeState, 
                   RuntimeStateElement, ASTElementPosition, SafepointCondition...

  identifiers.py   Structural identifier helpers (FNV-1a hashing, canonical
                   value rendering) used by AbstractSyntaxElement.assign_identifiers()

  operations.py    Operation / OperationArguments / OperationVariables and the
                   @operation decorator and loop() helper used to build chains
                   of resumable operations

  edit.py          EditScript and edit operations (Insert/Update/Delete) used to
                   modify a running abstract syntax tree

  vm.py            VirtualMachine: runs programs and applies EditScripts
                   (with RESTART / HOTSWAP option) to a running (live) execution

  lesp.py          Work-in-progress JSON-RPC server for a "live execution"
                   protocol (editor integration)

languages/         One package per supported language

  minilogo/
    runtime.py     Runtime state metamodel (Drawing, PenState, Scope, ...)
    syntax.py      Abstract syntax metamodel + evaluate() implementations

  robot/
    runtime.py     Runtime state metamodel (Maze, Robot, MazeCell, ...)
    syntax.py      Abstract syntax metamodel + evaluate() implementations

tools/
  export.py        Exports pythonic style pyecore classes to a single .ecore file
  visualization.py Script to generate visualization of .ecore files

tests/             pytest test suite; the Robot languages is exercised through the 
                   VirtualMachine API as usage examples (see tests/test_robot.py)
```

## Setup

**Step 1:** install **uv**, the Python package and project manager.

On Unix systems:
```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Refer to [UV's documentation](https://docs.astral.sh) for more information.

**Step 2:** create a Python virtual environment

```shell
uv venv
```

**Step 3:** activate the virtual environment

On Unix systems:
```shell
source .venv/bin/activate
```

**Step 4:** pull the project's dependencies

```shell
uv sync
```

## Running the tests

The test suite is the best place to see the VM in action, run it using the
following command:

```shell
uv run pytest
```
**Note**: running the pytest command as a python module is important so that other modules required
by the test suite are recognized.

`tests/test_robot.py` builds a Robot program (a maze definition plus a sequence
of commands), runs it through `VirtualMachine.init()`/`run()`, and asserts on
the resulting `RuntimeState`. It also demonstrates applying an `EditScript` to
replace part of the program while it runs, and `RESTART` it.

## Supporting a new language

A language composed of pyecore metamodels and `evaluate()` implementations.
There is no parser/grammar generation step at the moment: abstract syntax trees
are built directly as pyecore object graphs (e.g. in tests). In the future they
could be produced by a front-end which could be plugged-in later.

To add a language `languages/<name>`:

**Step 1 — Runtime state (`languages/<name>/runtime.py`)**

Define the EClasses that represent the state the program manipulates while
running. Each top-level state element is a `RuntimeStateElement` (from
`core.language`) with a `name`; these elements are looked up by name on
`RuntimeState` (e.g. `runtime.maze`, `runtime.penstate`). Use plain
`EObject`/`EClass`/`EEnum` for any supporting value types (positions, colors,
cells, ...).

**Step 2 — Abstract syntax (`languages/<name>/syntax.py`)**

Define the EClasses of your abstract syntax tree, each extending
`AbstractSyntaxElement` from `core.language`. Every node that can be executed
implements:

```python
def evaluate(self, runtime: RuntimeState) -> None:
    ...
```

- For a leaf/terminal command, decorate `evaluate` with `@operation()` (from
  `core.operations`) and read/mutate `runtime` directly — see `TurnLeft`,
  `MoveForward` or `Pen` in `languages/robot/syntax.py` /
  `languages/minilogo/syntax.py`.
- For nodes whose evaluation depends on the result of evaluating
  sub-expressions, use
  `@operation(arg_name=lambda node, runtime: node.sub_expr.evaluate(runtime), ...)`
  — the results are injected as keyword arguments into `evaluate`, see
  `BinaryExpression` or `Move`.
- For a sequence of commands (e.g. a `Program` or a block body), return
  `lazy_loop(self.commands, lambda cmd: cmd.evaluate(runtime))` to chain their
  operations.
- For a conditional repetition (while-loop), pass a `condition` Operation as the
  third argument to `lazy_loop(...)`, see `RepeatWhile`.
- For branching (if/else), splice the chosen branch's operations into the chain
  using the `_op` keyword parameter, see `IfDoElse`.

The root `Program` node's `evaluate()` should initialize `runtime.elements` with
the language's `RuntimeStateElement` instances before returning the chain of
operations for its commands.

**Step 3 — Run it**

```python
from core.vm import VirtualMachine

vm = VirtualMachine()
vm.scenario = Scenario(program_definition=...,program_command=...)
vm.init()
vm.run()

state = vm.state  # the RuntimeState after execution
```

Assign each `AbstractSyntaxElement` a unique `identifier` if you intend to
target it later with an `EditScript` (`InsertSyntaxOperation`,
`UpdateSyntaxOperation`, `DeleteSyntaxOperation`), applied through
`vm.udpate(...)`.

**Step 4 — (optional) Export the metamodel**

```shell
python -m tools.export languages.<name>.runtime languages.<name>.syntax -o <name>.ecore -n <name>
```

This collects all EClasses/EEnums defined in the given modules (and anything
they reference) into a single, self-contained `.ecore` file, e.g. `robot.ecore`.

*tool/export.py was generated by Claude Sonnet 4.6*
