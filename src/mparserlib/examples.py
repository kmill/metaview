# examples.py
# Feb 2012, Kyle Miller

from lexer import *
from parser import *

import operator

const = lambda x : lambda _ : x
unarg = lambda f : lambda x : f(*x)
tokval = lambda x: x.value
tokkind = lambda k : satisfy(lambda x: x.kind == k).expectsMsg(k) >> tokval

getItem = lambda i : lambda x : list(x)[i]

symb = lambda s : a(Token('symbol', s))
punct = lambda s : skip(a(Token('punct', s))).expectsMsg(repr(s))


def calculator(s) :
    lexer = Lexer([
            Spec(None,  r'[ \t\r\n]+|//.*'), # whitespace
            Spec('number', r'(([0-9]+(\.[0-9]*)?|\.[0-9]+))([Ee][+\-]?[0-9]+)?'),
            Spec('punct', r'[(),]'),
            Spec('op', r'[+\-*/%^]'),
            Spec('symbol', r'[a-z]+'),
            ])
    tokens = lexer.tokenize(s)

    op_ = lambda s : skip(a(Token('op', s))).expectsMsg(repr(s))

    def eval(first, rest) :
        for f, v in rest :
            first = f(first, v)
        return first

    def makeBinOp(opdict, next) :
        """Takes a dict of opsymbol->binaryfunction pairs and creates
        a left-associative parser for them."""
        op = reduce(operator.or_, [
                a(Token('op', k)).expectsMsg(repr(k)) >> const(v)
                for k,v in opdict.iteritems()
                ])
        return (next + many((op + next) >> tuple)) \
            >> unarg(eval)

    ops = [{"^" : operator.pow},
           {"*" : operator.mul, "/" : operator.div, "%" : operator.mul},
           {"+" : operator.add, "-" : operator.sub},
           ]

    def makeBinOps(ops, last) :
        next = last
        for prec in ops :
            if prec :
                next = makeBinOp(prec, next)
        return next

    expr = FwdDecl()

    def eval_func(fname, args) :
        import math
        return math.__dict__[fname](*args)
    func = (tokkind("symbol") + between(punct("("), punct(")"), sepby(expr, punct(",")) >> tuple)) \
        >> unarg(eval_func)

    nullary = \
        (punct("(") + expr + punct(")")) \
        | (tokkind("number") >> float) \
        | ((op_("-") + expr) >> operator.neg) \
        | func

    binop = makeBinOps(ops, nullary)
    expr.define(binop)

    toplevel = expr + eof

    return toplevel.parse(tokens)


def repl_calculator() :
    while True :
        s = raw_input("> ")
        try :
            print calculator(s)
        except LexerError as x :
            print x
        except ParserError as x :
            print x

if __name__=="__main__" :
    repl_calculator()
