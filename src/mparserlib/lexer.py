# lexer.py
# Feb 2012, Kyle Miller

__all__ = ["LexerError", "Token", "Lexer", "Spec"]

import re

class LexerError(Exception) :
    def __init__(self, pos, unexpected) :
        self.args = [pos, unexpected]
    @property
    def pos(self) :
        return self.args[0]
    def __str__(self) :
        line, column = self.pos
        unexpected = self.args[1]
        fmt = (unexpected, line, column)
        return "unexpected %r at line %r, column %r" % fmt

class Token(object) :
    def __init__(self, kind, value, pos=None) :
        self.pos = pos
        self.kind = kind
        self.value = value
    def __repr__(self) :
        return "Token(%r, %r, pos=%r)" % (self.kind, self.value, self.pos)
    def __str__(self) :
        return "%s \"%s\"" % (self.kind, self.value)
    def __eq__(self, other) :
        return (type(self) == type(other)
                and self.kind == other.kind
                and self.value == other.value)

class Lexer(object) :
    def __init__(self, lex_specs) :
        self.lex_specs = lex_specs
    def tokenize(self, s) :
        length = len(s)
        line, col = 1, 0
        i = 0
        while i < length :
            for spec in self.lex_specs :
                res = spec.re.match(s, i)
                if res :
                    pos = (line, col)
                    text = res.group()
                    newlines = text.count("\n")
                    line += newlines
                    i += len(text)
                    if newlines :
                        col = len(text) - text.rfind("\n") - 1
                    else :
                        col += len(text)
                    if spec.kind :
                        yield Token(spec.kind, text, pos)
                    break
            else :
                raise LexerError((line, col), s[i])

class Spec(object) :
    def __init__(self, kind, regexp, flags=0) :
        self.kind = kind
        self.re = re.compile(regexp, flags=flags)
