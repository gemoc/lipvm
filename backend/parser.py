from importlib import import_module

from antlr4 import CommonTokenStream, InputStream
from antlr4.tree.Tree import Tree

class Parser:

    def __init__(self, module):
        self._LanguageLexer = getattr(import_module(module + ".LanguageLexer"), 'LanguageLexer')
        self._LanguageParser = getattr(import_module(module + ".LanguageParser"), 'LanguageParser')

    def parse(self, code: str) -> Tree:
        lexer = self._LanguageLexer(InputStream(code))
        stream = CommonTokenStream(lexer)

        parser = self._LanguageParser(stream)
        #parser.removeErrorListeners()

        tree = parser.main()

        if parser.getNumberOfSyntaxErrors() > 0:
            raise Exception("Syntax errors") # TODO better error management

        return tree