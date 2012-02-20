# querylang.py
# language for querying the database

from mparserlib.lexer import *
from mparserlib.parser import *
import operator
import fuzzydate
import datetime
import re
import uuid
import blobs
import blobviews
import tornado.escape

string_regexps = {
    'squote' : r"'(\\[\\'\"]|[^'])*'",
    'dquote' : r"\"(\\[\\'\"]|[^\"])*\"",
    }

lexer = Lexer([
        Spec(None,  r'[ \t\r\n]+|//.*'), # whitespace
        Spec('string', r'%(squote)s|%(dquote)s' % string_regexps),
        Spec('symbol', r'\$[A-Za-z_]+'),
        Spec('key', r'@[a-zA-Z0-9][a-zA-Z0-9_]*'),
        Spec('text', r'[A-Za-z_0-9]+'),
        Spec('punctuation', r'[(){}:,\[\]]'),
        Spec('op', r'[=<>!]+'),
        ])

const = lambda x : lambda _ : x
unarg = lambda f : lambda x : f(*x)
tokval = lambda x: x.value
tokkind = lambda k : satisfy(lambda x: x.kind == k).expectsMsg(k) >> tokval

symb = lambda s : a(Token('symbol', s)).expectsMsg(repr(s))
op = lambda s : a(Token('op', s)).expectsMsg(repr(s))
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

ops = [{symb("$has") : binop("has"),
        op("=") : binop("has"),
        symb("$neq") : binop("neq"),
        op("!=") : binop("neq"),
        symb("$after") : binop("after"),
        op(">=") : binop("after"),
        symb("$before") : binop("before"),
        op("<=") : binop("before"),
        op(">") : binop("gt"),
        op("<") : binop("lt"),
        symb("$between") : binop("between"),
        symb("$in") : binop("in"),
        symb("$all") : binop("all"),
        symb("$contains") : binop("contains")},

       {symb("$and") : binop("and")},

       {symb("$or") : binop("or")},

       {op(">>") : binop("render")},
       ]

expr = FwdDecl()
text = many1((tokkind("string") >> unescape) | (tokkind("text"))) >> " ".join
key = tokkind("key") >> (lambda x : x[1:])
qtuple = between(punct("("), punct(")"), sepby(expr, punct(",")))
qlist = between(punct("["), punct("]"), sepby(expr, punct(","))) \
    >> (lambda x : ["list", x])
unarynot = (skip(symb("$not")) + expr) >> (lambda x : ["not", x])
parens = between(punct("("), punct(")"), expr)
func = (tokkind("symbol") + qtuple) >> unarg(lambda s, args : [s[1:]]+list(args))
nullary = key | text | parens | unarynot | func | qlist
binops = makeBinOps(ops, nullary)
expr.define(binops)
top_level_query = expr + eof

class QueryError(Exception) :
    pass

def translate(expr, env, glob) :
    if type(expr) in [str, unicode] :
        return ("value", expr)
    elif type(expr) is list :
        if expr[0] == "list" :
            return ("value", [translate(e, env, glob) for e in expr[1]])
        try :
            func = env[expr[0]]
        except :
            raise QueryError("Unknown function",expr[0])
        try :
            return func(env, glob, *[translate(e,env,glob) for e in expr[1:]])
        except TypeError as x :
            raise QueryError("TypeError",x)
        except AssertionError as x :
            raise QueryError("Type error for "+expr[0] + ". " + x.args[0])
    else :
        raise QueryError("Unknown query type",expr)

def add_to_env(env, name) :
    def _add_to_env(f) :
        def __add_to_env(env, glob, *args, **kwargs) :
            return f(*args, **kwargs)
        env[name] = __add_to_env
        return __add_to_env
    return _add_to_env

def add_to_env_with_state(env, name) :
    def _add_to_env(f) :
        env[name] = f
        return f
    return _add_to_env

env = {}

def require_type(type, *args) :
    assert all(a[0] == type for a in args), "requires "+type
    return (a[1] for a in args)

@add_to_env(env, "date")
def q_date(s=("value",""), now=None) :
    """Takes s="" and now=datetime.now() and gives
    fuzzydate.parse_date(s,now)."""
    if now is None :
        now = ("value", datetime.datetime.now())
    s, now = require_type("value", s, now)
    return ("value", fuzzydate.parse_date(s, now))
@add_to_env(env, "daterange")
def q_daterange(start, end, now=None) :
    """Takes (startdate, enddate) and creates [$date(startdate),
    $date(enddate)]."""
    if now is None :
        now = ("value", datetime.datetime.now())
    now, start, end = require_type("value", now, start, end)
    start = fuzzydate.parse_date(start, now)
    end = fuzzydate.parse_date(end, now)
    return ("value", [("value", start), ("value", end)])
@add_to_env(env, "re")
def q_re(r, ops=("value","")) :
    """Takes a regular expression and possibly some options (from
    "imsux" for ignorecase, multiline, dotall, unicode, verbose,
    respectively) and compiles the regular expression."""
    r, ops = require_type("value", r, ops)
    options = 0
    op_dict = {"i" : re.I, "m" : re.M, "s" : re.S,
               "u" : re.U, "x" : re.X}
    for o in ops :
        options |= op_dict.get(o, 0)
    return ("value", re.compile(r, options))
@add_to_env_with_state(env, "contains")
def q_contains(env, glob, key, s, ops=("value","")) :
    """Takes a key and a string and makes sure key contains the string
    using a regular expression"""
    key, s = require_type("value", key, s)
    t, r = q_re(env, glob, ("value", ".*%s.*" % s), ops=ops)
    return ("query", {key : r})
@add_to_env(env, "UUID")
def q_UUID(u) :
    """Just runs UUID on the argument."""
    u = list(require_type("value", u))[0]
    return ("value", uuid.UUID(u))

@add_to_env(env, "exists")
def q_exists(key) :
    key = list(require_type("value", key))[0]
    return ("query", {key : {"$exists" : True}})
@add_to_env(env, "notexists")
def q_exists(key) :
    key = list(require_type("value", key))[0]
    return ("query", {key : {"$exists" : False}})

@add_to_env(env, "and")
def q_and(*args) :
    args = require_type("query", *args)
    return ("query", {"$and" : list(args)})
@add_to_env(env, "or")
def q_and(*args) :
    args = require_type("query", *args)
    return ("query", {"$or" : list(args)})

@add_to_env(env, "after")
def q_after(key, value) :
    """(field $after value) for (field >= value)"""
    key, value = require_type("value", key, value)
    return ("query", {key : {"$gte" : value}})
@add_to_env(env, "before")
def q_before(key, value) :
    """(field $before value) for (field <= value)"""
    key, value = require_type("value", key, value)
    return ("query", {key : {"$lte" : value}})
@add_to_env(env, "between")
def q_between(key, value) :
    """(field $between [start,end])"""
    key, value = require_type("value", key, value)
    a, b = require_type("value", *value)
    return ("query", {key : {"$gte" : a, "$lte" : b}})
@add_to_env(env, "gt")
def q_gt(key, value) :
    """(field > value)"""
    key, value = require_type("value", key, value)
    return ("query", {key : {"$gt" : value}})
@add_to_env(env, "lt")
def q_lt(key, value) :
    """(field < value)"""
    key, value = require_type("value", key, value)
    return ("query", {key : {"$lt" : value}})

@add_to_env(env, "has")
def q_has(key, value) :
    """(field $has value)"""
    key, value = require_type("value", key, value)
    return ("query", {key : value})
@add_to_env(env, "neq")
def q_neq(key, value) :
    """(field $neq value)"""
    key, value = require_type("value", key, value)
    return ("query", {key : {"$ne" : value}})


@add_to_env(env, "in")
def q_in(key, value) :
    """(field $in value) for (field in values)"""
    key, value = require_type("value", key, value)
    value = list(require_type("value", *value))
    return ("query", {key : {"$in" : value}})

@add_to_env(env, "all")
def q_all(key, value) :
    """(field $all value) for (field has all values)"""
    key, value = require_type("value", key, value)
    value = list(require_type("value", *value))
    return ("query", {key : {"$all" : value}})

@add_to_env(env, "not")
def q_not(expr) :
    """Negates an expression"""
    expr = list(require_type("query", expr))
    return ("query", {"$not" : expr[0]})

def force_to_blobs(glob, blobs) :
    if blobs[0] == "query" :
        blobs = "blobs", perform_db_query(glob["db"], glob["blob_base"], blobs[1])
    return list(require_type("blobs", blobs))[0]

@add_to_env_with_state(env, "sort")
def q_sort(env, glob, blobs, key=("value", "created"), dir=("value", "asc")) :
    blobs = force_to_blobs(glob, blobs)
    key, dir = require_type("value", key, dir)
    dir = 1 if dir[0] == "a" else -1
    def scmp(x, y) :
        v = cmp(type(x), type(y))
        if v == 0 : return cmp(x, y)
        return v
    blobs = sorted(blobs, cmp=lambda x,y : dir*scmp(x,y), key=lambda b: b["tags"].get(key, 0))
    return "blobs", blobs

def translate_query(q, glob) :
    """takes a string and executes the query program up until the last
    value.  see run_query for one that executes to completion."""
    return translate(top_level_query.parse(lexer.tokenize(q)), env, glob)

@add_to_env_with_state(env, "r")
def q_r(env, glob, renderer, *args) :
    tmp = list(require_type("value", renderer, *args))
    renderer, args = tmp[0], tmp[1:]
    if renderer not in glob["renderers"] :
        raise QueryError("No such renderer",renderer)
    return "renderer", glob["renderers"][renderer](glob, *args)

@add_to_env_with_state(env, "render")
def q_render(env, glob, blobs, renderer) :
    blobs = force_to_blobs(glob, blobs)
    renderer = list(require_type("renderer", renderer))[0]
    return ("html", renderer(blobs))

@add_to_env_with_state(env, "perform_db_query")
def q_perform_db_query(env, glob, query) :
    """Runs perform_query.  Takes a query and gives the corresponding blobs."""
    return "blobs", force_to_blobs(glob, blobs)

def perform_db_query(db, blob_base, query) :
    """Runs a query (which is the output of translate_query) and gives
    the blobs."""
    search_defaults = {"blob_base" : blob_base, "_masked" : False}
    sort = [("created", -1)]
    query = query.copy()
    query.update(search_defaults)
    the_blobs = list(blobs.Blob.find_by_tags(db, query, sort))
    return the_blobs

def run_query(render_string, db, renderers, blob_base, s) :
    glob = {"db" : db,
            "blob_base" : blob_base,
            "renderers" : renderers,
            "render_string" : render_string,
            }
    try :
        t, res = translate_query(s, glob)
        if t == "value" and type(res) in [str, unicode] :
            t = "query"
            res = {"title" : res}
        if t == "query" :
            the_blobs = perform_db_query(db, blob_base, res)
            if not the_blobs :
                return "<p>No results.</p>"
            bs = "\n".join(blobviews.blob_to_html(render_string, b, {}) for b in the_blobs)
            return bs
        elif t == "value" :
            return "Result: "+str(res)
        elif t == "html" :
            return res
        elif t == "blobs" :
            if not res :
                return "<p>No results.</p>"
            bs = "\n".join(blobviews.blob_to_html(render_string, b, {}) for b in res)
            return bs
        else :
            raise QueryError("Result of query is wrong type", t)
    except LexerError as x :
        out = []
        out.append("<div class=\"queryerror\"><p><strong>Lexer error</strong></p></div>")
        row, column = x.pos
        line = s.split("\n")[row-1]
        out.append("<pre>"+tornado.escape.xhtml_escape(line)+"\n")
        out.append(" "*(column) + "^</pre>")
        return "".join(out)
    except ParserError as x :
        out = ["<div class=\"queryerror\"><p><strong>Parser error</strong></p>",
               str(x).replace("\n", "<br/>")]
        row, column = x.pos
        line = s.split("\n")[row-1]
        out.append("<pre>"+tornado.escape.xhtml_escape(line)+"\n")
        out.append(" "*(column) + "^</pre></div>")
        return "".join(out)
    except QueryError as x :
        error = "<div class=\"queryerror\"><p><strong>Query error</strong></p>" \
            + str(x).replace("\n", "<br/>") + "</div>"
        return error


#    t = r"(tags $has 'recipe') $and (created $after $date(2 feb 2012))"
#    t = ""

if __name__=="__main__" :
    while True :
        t = raw_input("> ")
        try :
            tokens = list(lexer.tokenize(t))
            #print "tokens:", tokens
            parsed = top_level_query.parse(tokens)
            #print "parsed:", parsed
            res = translate(parsed, env, {})
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
