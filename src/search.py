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


from funcparserlib.lexer import make_tokenizer, Token, LexerError
from funcparserlib.parser import (a, maybe, many, skip, eof,
                                  fwd, ParserError)

string_regexps = {
    'squote' : r"'(\\[\\'\"]|[^'])*'",
    'dquote' : r"\"(\\[\\'\"]|[^\"])*\"",
    }

lex_specs = [
    ('Space',  (r'[ \t\r\n]+',)),
    ('String', (r'%(squote)s|%(dquote)s' % string_regexps,)),
    ('Symbol', (r'\$[A-Za-z]+',)),
    ('Text',   (r'[A-Za-z_0-9]+',)),
    ('Punctuation', (r'[(){}:,]',))
    ]

def tokenizer(str, t=make_tokenizer(lex_specs)) :
    useless = ['Space']
    return [x for x in t(str) if x.type not in useless]

const = lambda x : lambda _ : x
unarg = lambda f : lambda x : f(*x)
tokval = lambda x: x.value
toktype = lambda t : some(lambda x: x.type == t) >> tokval

symb = lambda s : a(Token('Symbol', s)) >> tokval
punct = lambda s : skip(a(Token('Punctuation', s)))

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

expr = fwd

text = many((toktype("String") >> unescape) | (toktype("Text"))) >> " ".join

cexpr = punct(",") + expr
parens = punct("(") + expr + many(cexpr) + punct(")")

top_level = expr + eof

expr.define(text | parens)

try :
    t = r"(tags $has 'recipe') $and (created $after $date(2 feb 2012))"
    t = "(hi, there)"
    tokens = tokenizer(t)
    print "tokens:",tokens
    print "parsed:",top_level.parse(tokens)
except LexerError as x :
    print "Lexer error"
    row, column = x.pos
    line = t.split("\n")[row-1]
    print line
    print " "*(column) + "^"
