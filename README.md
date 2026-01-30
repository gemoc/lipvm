# LESP - Language Execution Server Protocol

A JSON-RPC based server for executing custom languages on the LipVM stack machine. LESP provides IDE integration, step-by-step debugging, and time-travel execution.

## Overview

LESP is a language-agnostic execution server that:
- Compiles source code using configurable language modules
- Executes programs on the LipVM stack machine
- Provides step-by-step debugging (forward and backward)
- Exposes a JSON-RPC API for IDE integration
- Supports multiple programming languages

## Components

- **LESP Server**: JSON-RPC protocol server for IDE integration
- **LipVM**: Stack-based virtual machine for executing bytecode
- **Language Modules**: Pluggable language implementations (e.g., MiniLogo)
- **VS Code Extension**: Language-agnostic extension for running programs

## Quick Start

### Installation

**Step 1:** Install **uv** the Python package and project manager. 

On unix system use the following command:  
```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Refer to [UV's documentation](https://docs.astral.sh) for more information.  

**Step 2:** Create a Python virtual environment

```shell
uv venv
```

**Step 3:** Activate the virtual environment

On Unix systems:
```shell
source .venv/bin/activate
```

On Windows:
```shell
.venv\Scripts\activate
```

**Step 4:** Install the package

```shell
uv sync
```

### Usage

#### Start LESP Server

```shell
# Start with default language (minilogo)
lesp

# Start with specific language module
lesp --language-module languages.minilogo
```

#### Run LipVM Directly

```shell
# Run a file directly (without server)
lipvm languages/minilogo/examples/example.logo

# Run with specific language module
lipvm --language-module languages.minilogo file.logo
```

#### Try MiniLogo IDE

```shell
python -m languages.minilogo.ide.Minilogo
```

## LESP Protocol

LESP uses JSON-RPC over stdin/stdout. See `lesp/README.md` for full protocol documentation.

### Example Session

```bash
# Start the server
lesp

# Send requests (one per line)
{"id":1,"method":"compile","params":{"code":"pen down\nmove 100 100"}}
{"id":2,"method":"start","params":{}}
{"id":3,"method":"stepForward","params":{}}
{"id":4,"method":"getState","params":{}}
```

### Supported Methods

- `setLanguageModule` - Configure language to use
- `compile` - Compile source code to bytecode
- `start` - Start execution
- `stepForward` - Step forward one instruction
- `stepBackward` - Step backward one instruction
- `getState` - Get current execution state

## VS Code Extension

A language-agnostic VS Code extension is available in the `extension/` folder:

```bash
cd extension
npm install
npm run compile
# Press F5 in VS Code to launch
```

Features:
- Configure any language by file extension and compiler path
- One-click program execution
- Output visualization
- Persistent workspace configuration

See `extension/README.md` for details.

## Creating a Language

### Step 1: Generate Parser

**Requirements:**
- An ANTLR4 grammar file, e.g. `languages/mylang/syntax/Language.g4`
  - Grammar must be named: **Language**
  - Root parsing rule must be named: **start**
- Java 21 or superior
- `antlr-4.13.2-complete.jar` from https://www.antlr.org/download.html

```shell
java -jar antlr-4.13.2-complete.jar -Dlanguage=Python3 \
  languages/mylang/syntax/Language.g4 -no-listener -visitor
```

This generates an AST visitor: `languages/mylang/syntax/LanguageVisitor.py`

### Step 2: Implement Compiler

Create a `Compiler` class in your language directory: `languages/mylang/Compiler.py`

```python
from backend.Bytecode import Bytecode
from backend.instructions.Value import Value

class Compiler:
    def compile(self, ast):
        self._bytecode = Bytecode()
        # Visit AST and add instructions
        self.visit(ast)
        return self._bytecode
```

### Step 3: Define Instructions

Create instruction classes that implement `execute(self, stack, global_variables, heap)`:

```python
from backend.instructions.AbstractInstruction import AbstractInstruction

class MyInstruction(AbstractInstruction):
    def execute(self, stack, global_variables, heap):
        # Define instruction behavior
        value = stack.pop()
        # ... do something
        stack.push(result)
```

### Step 4: Use Your Language

```bash
# Run directly
lipvm --language-module languages.mylang file.mylang

# Or via LESP server
lesp --language-module languages.mylang
```

## Example: MiniLogo

MiniLogo is a turtle graphics language included as an example:

```logo
pen down
move 100 100
color #FF0000
move 200 200
pen up
```

Try it:
```bash
lipvm languages/minilogo/examples/example.logo
```

## Project Structure

```
lesp/
├── lesp/              # LESP server (main package)
│   ├── server.py     # JSON-RPC server implementation
│   └── README.md     # Protocol documentation
├── backend/           # LipVM virtual machine (library)
│   ├── LipVM.py      # VM core
│   ├── Bytecode.py   # Bytecode container
│   ├── Execution.py  # Execution engine
│   ├── Stack.py      # Stack implementation
│   └── instructions/ # Base instruction classes
├── languages/         # Language implementations
│   └── minilogo/     # MiniLogo example
│       ├── Compiler.py
│       ├── syntax/   # ANTLR generated files
│       └── instructions/
├── extension/        # VS Code extension
└── pyproject.toml    # Package configuration
```

## Development

### Debug with debugpy

```shell
python -m debugpy --wait-for-client --listen 5678 backend/LipVM.py file.logo
```

VSCode `launch.json` configuration:

```json
{
  "version": "0.2.0",
  "configurations": [
      {
          "name": "Python Debugger: Remote Attach",
          "type": "debugpy",
          "request": "attach",
          "connect": {
              "host": "localhost",
              "port": 5678
          }
      }
  ]
}
```

### Testing

```bash
# Test LipVM directly
lipvm languages/minilogo/examples/example.logo

# Test LESP server
python test_lesp.py

# Check server logs
tail -f lipvm-server.log
```

## Documentation

- [LESP Protocol](lesp/README.md) - Full protocol specification
- [VS Code Extension](extension/README.md) - Extension usage guide
- [Refactoring Notes](LESP_REFACTORING.md) - Architecture details

## Architecture

```
┌─────────────────┐
│   IDE/Editor    │
│  (VS Code, etc) │
└────────┬────────┘
         │ JSON-RPC
         │
┌────────▼────────┐
│  LESP Server    │  ← Main Package
│  (lesp/server)  │
└────────┬────────┘
         │ Python API
         │
┌────────▼────────┐
│     LipVM       │  ← Library
│  (backend/*)    │
└────────┬────────┘
         │
┌────────▼────────┐
│   Language      │  ← Pluggable
│   Compiler      │
│ (languages/*)   │
└─────────────────┘
```

## License

See LICENSE file for details.
