# LipVM

## Import the project

**Step 1:** install **uv** the Python package and project manager. 

On unix system use the following command:  
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

On Windows:

```shell
.venv\Scripts\activate
```

**Step 4:** pull project's dependencies

```shell
uv sync
```

## Generate parser and visitor for a language

**Requirements:**

- An ANTLR4 grammar file, e.g. `languages/minilogo/Language.g4`.
  - For now the grammar must be named: **Language**.
  - The root parsing rule must be named **start**. 
- A Java installation, version 21 or superior.
- The `antlr-4.13.2-complete.jar` from https://www.antlr.org/download.html.

```shell
java -jar antlr-4.13.2-complete.jar -Dlanguage=Python3 languages/minilogo/syntax/Language.g4 -no-listener -visitor
```

Upon the execution of this command, an AST visitor is generated: see `languages/minilogo/LanguageVisitor.py`.  

## Specify the semantic of a language

**Step 1:** Copy the generated visitor, in the directory of your language and rename the file and class to `LanguageInterpreter`.  
Example: `languages/minilogo/LanguageInterpreter.py`.  

**Step 2:** Modify the `LanguageInterpreter` class definition to extend `Interpreter` from the `backend.interpreter` module.

**Step 3:** Create a constructor for the `LanguageInterpreter` class that takes a parameter of type `Parser` from `backend.parser` and invoke the parent constructor with it.  
Example: `super().__init__(parser)`

**Step 4:** Define the semantic of your language in the visit methods. The interpreter requires to use Python generators through:
  - The **yield** keyword when visiting a subtree: `yield self.visit(tree)`, `yield self.visitChildren(tree)`.
  - The **yield** keyword instead of standard **return** when defining a method's return value.

The interpreter also expect all values manipulated by the execution to be declared as attributes of the `self._environment` object inherited from the `Interpreter` class.

## Debug

To debug, for now I use `debugpy` using the following command taking the module of my language to import `file.logo` (a logo code file) in argument:

```shell
python -m debugpy --wait-for-client --listen 5678 main.py "languages.minilogo"
```

Using VSCode you can use the following `launch.json` configuration to connect to the debugging session:

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

## Try Minilogo IDE

To start the currently implemented LipVM with Minilogo, execute the following command:

```shell
python -m languages.minilogo.MinilogoIDE
```