from importlib import import_module

from antlr4 import CommonTokenStream, InputStream
from antlr4.tree.Tree import Tree

class Parser:

    def __init__(self, module):
        self._LanguageLexer = getattr(import_module(module + ".LanguageLexer"), 'LanguageLexer')
        self._LanguageParser = getattr(import_module(module + ".LanguageParser"), 'LanguageParser')
        try:
            self._languageVisitorSteps = getattr(import_module(module + ".LanguageVisitorSteps"), 'LanguageVisitorSteps')()
        except Exception:
            self._languageVisitorSteps = None

    def parse(self, code: str) -> Tree:
        lexer = self._LanguageLexer(InputStream(code))
        stream = CommonTokenStream(lexer)

        parser = self._LanguageParser(stream)
        parser.removeErrorListeners()

        tree = parser.main()

        if parser.getNumberOfSyntaxErrors() > 0:
            raise Exception("Syntax errors")

        if self._languageVisitorSteps is not None:
            self._languageVisitorSteps.visit(tree)

        return tree