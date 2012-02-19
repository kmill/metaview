# querylang.py
# language for querying the database

from mparserlib.lexer import *
from mparserlib.parser import *
import operator
import fuzzydate
import datetime

string_regexps = {
    'squote' : r"'(\\[\\'\"]|[^'])*'",
    'dquote' : r"\"(\\[\\'\"]|[^\"])*\"",
    }

lexer = Lexer([
        Spec(None,  r'[ \t\r\n]+|//.*'), # whitespace
        Spec('string', r'%(squote)s|%(dquote)s' % string_regexps),
        Spec('symbol', r'\$[A-Za-z]+'),
        Spec('text', r'[A-Za-z_0-9]+'),
        Spec('punctuation', r'[(){}:,]'),
        Spec('op', r'[=<>]+'),
        ])

const = lambda x : lambda _ : x
unarg = lambda f : lambda x : f(*x)
tokval = lambda x: x.value
tokkind = lambda k : satisfy(lambda x: x.kind == k).expectsMsg(k) >> tokval

symb = lambda s : a(Token('symbol', s)).expectsMsg(repr(s))
punct = lambda s : skip(a(Token('punctuation', s))).expectsMsg(repr(s))

def unescape(s) :
    """Unescapes a string which is surrounded in quotes."""
    out = []
    i = 1
    while i < len(s)-1 :
        if s[i] == "\\" :
            out.append(s[i+1])
            i += 2
        else :
            try :
                j = s.index("\\", i)
            except ValueError :
                j = len(s)-1
            out.append(s[i:j])
            i = j
    return "".join(out)

def makeBinOp(opdict, next) :
    """Takes a dict of opsymbol->binaryfunction pairs and creates
    a left-associative parser for them."""
    def eval(first, rest) :
        for f, v in rest :
            first = f(first, v)
        return first
    op = reduce(operator.or_, [k >> const(v) for k,v in opdict.iteritems()])
    return (next + many((op + next) >> tuple)) \
        >> unarg(eval)
def makeBinOps(ops, last) :
    next = last
    for prec in ops :
        if prec :
            next = makeBinOp(prec, next)
    return next


def binop(name) :
    def _binop(a,b) :
        return [name, a, b]
    return _binop

ops = [{symb("$has") : binop("has"), symb("$after") : binop("after"), symb("$is") : binop("is")},
       {symb("$and") : binop("and")},
       {symb("$or") : binop("or")}
       ]

expr = FwdDecl()
text = many1((tokkind("string") >> unescape) | (tokkind("text"))) >> " ".join
qtuple = between(punct("("), punct(")"), sepby(expr, punct(",")))
parens = between(punct("("), punct(")"), expr)
func = (tokkind("symbol") + qtuple) >> unarg(lambda s, args : [s[1:]]+list(args))
nullary = text | parens | func
binops = makeBinOps(ops, nullary)
expr.define(binops)
top_level = expr + eof

class QueryError(Exception) :
    pass

def translate(expr, env) :
    if type(expr) is str :
        return expr
    elif type(expr) is list :
        try :
            func = env[expr[0]]
        except :
            raise QueryError("Unknown function",expr[0])
        try :
            return func(*[translate(e,env) for e in expr[1:]])
        except TypeError as x :
            raise QueryError("TypeError",x)
    else :
        raise QueryError("Unknown query type",expr)

#    t = r"(tags $has 'recipe') $and (created $after $date(2 feb 2012))"
#    t = ""

def add_to_env(env, name) :
    def _add_to_env(f) :
        env[name] = f
        return f
    return _add_to_env

env = {}

@add_to_env(env, "date")
def q_date(s="", now=None) :
    if now is None :
        now = datetime.datetime.now()
    return fuzzydate.parse_date(s, now)

if __name__=="__main__" :
    while True :
        t = raw_input("> ")
        try :
            tokens = list(lexer.tokenize(t))
            #print "tokens:", tokens
            parsed = expr.parse(tokens)
            #print "parsed:", parsed
            res = translate(parsed, env)
            print "translated:",res
        except LexerError as x :
            print "Lexer error"
            row, column = x.pos
            line = t.split("\n")[row-1]
            print line
            print " "*(column) + "^"
        except ParserError as x :
            print str(x)
        except QueryError as x :
            print str(x)
