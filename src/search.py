# search.py
# Feb 2012, Kyle Miller

# class SearchHandler(MVRequestHandler) :
#     @tornado.web.authenticated
#     def get(self, blob_base) :
#         search = { "blob_base" : blob_base, "_masked" : False }
#         sort = [("created", -1)]
#         query = self.get_argument("q", "")
#         parts = query.split(",")
#         for part in parts :
#             if part :
#                 kv = part.split("=", 2)
#                 if len(kv) == 1 :
#                     k, v = "tag", kv[0]
#                 else :
#                     k, v = kv
#                 if k[0] == "<" :
#                     k = k[1:]
#                     sort.append((k,1))
#                 if k[0] == ">" :
#                     k = k[1:]
#                     sort.append((k,-1))
#                 search[k] = v.strip() #{ "$regex" : v, "$options" : 'i' }
#         print search, sort
#         the_blobs = list(blobs.Blob.find_by_tags(self.db, search, sort))
#         self.render("search.html", the_blobs=the_blobs, query=query)

from mparserlib.lexer import *
from mparserlib.parser import *
import operator

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

#    t = r"(tags $has 'recipe') $and (created $after $date(2 feb 2012))"
#    t = ""

if __name__=="__main__" :
    while True :
        t = raw_input("> ")
        try :
            tokens = list(lexer.tokenize(t))
            #print "tokens:", tokens
            parsed = expr.parse(tokens)
            print "parsed:", parsed
        except LexerError as x :
            print "Lexer error"
            row, column = x.pos
            line = t.split("\n")[row-1]
            print line
            print " "*(column) + "^"
        except ParserError as x :
            print str(x)
