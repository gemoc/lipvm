import sys
import importlib
from antlr4 import *

from backend.Environment import Environment
from backend.Execution import Execution

class LipVM:

    def __init__(self, language_module="languages.minilogo"):
        """Initialize LipVM with a language module.
        
        Args:
            language_module: Python module package path (e.g., "languages.minilogo")
        """
        # Import the language module
        lang = importlib.import_module(language_module)
        
        # Import submodules to retrieve the lexer, parser, and compiler
        syntax_lexer = importlib.import_module(f"{language_module}.syntax.LanguageLexer")
        syntax_parser = importlib.import_module(f"{language_module}.syntax.LanguageParser")
        compiler = importlib.import_module(f"{language_module}.Compiler")
        
        # Retrieve the classes from the imported modules
        self.LanguageLexer = getattr(syntax_lexer, "LanguageLexer")
        self.LanguageParser = getattr(syntax_parser, "LanguageParser")
        Compiler = getattr(compiler, "Compiler")
        
        self._compiler = Compiler()
        self._executions = []

    def compile(self, stream):
        """Compile an ANTLR input stream into an Execution object.
        
        Args:
            stream: ANTLR InputStream, FileStream, or CommonTokenStream
            
        Returns:
            Execution object ready to run
            
        Raises:
            Exception: If syntax errors are found
        """
        lexer = self.LanguageLexer(stream)
        stream = CommonTokenStream(lexer)
        
        parser = self.LanguageParser(stream)
        parser.removeErrorListeners()

        tree = parser.start()

        if parser.getNumberOfSyntaxErrors() > 0:
            raise Exception("Syntax errors")
        
        return Execution(self._compiler.compile(tree), Environment())

    def compile_file(self, path):
        """Compile a source file into an Execution object.
        
        Args:
            path: Path to the source file
            
        Returns:
            Execution object ready to run
        """
        return self.compile(FileStream(path))
    
    def compile_code(self, code):
        """Compile source code string into an Execution object.
        
        Args:
            code: Source code as a string
            
        Returns:
            Execution object ready to run
        """
        return self.compile(InputStream(code))


def main():
    """CLI entry point for LipVM - compile and execute source files."""
    if len(sys.argv) < 2:
        print("Usage: lipvm [--language-module MODULE] <file>")
        print("       lipvm <file>  # uses default: languages.minilogo")
        print()
        print("Examples:")
        print("  lipvm file.logo")
        print("  lipvm --language-module languages.minilogo file.logo")
        print()
        print("For server mode, use: lesp --language-module MODULE")
        sys.exit(1)
    
    # Parse optional language module argument
    language_module = "languages.minilogo"  # default
    file_path = sys.argv[1]
    
    if sys.argv[1] == "--language-module" and len(sys.argv) > 3:
        language_module = sys.argv[2]
        file_path = sys.argv[3]
    
    try:
        vm = LipVM(language_module)
        execution = vm.compile_file(file_path)
        execution.start()
        print(execution.environment)
    except ImportError as e:
        print(f"Error: Failed to load language module '{language_module}': {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
