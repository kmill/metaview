# search.py
# Feb 2012, Kyle Miller

import querylang
class SearchHandler(MVRequestHandler) :
    @tornado.web.authenticated
    def get(self, blob_base) :
        search = { "blob_base" : blob_base, "_masked" : False }
        sort = [("created", -1)]
        query = self.get_argument("q", "")

        try :
            mongoquery = querylang.translate_query(query)
        except LexerError as x :
            out = []
            out.append("<p><strong>Lexer error</strong></p>")
            row, column = x.pos
            line = t.split("\n")[row-1]
            out.append("<pre>"+ line+"</pre>"
            print " "*(column) + "^"
        except ParserError as x :
            print str(x)
        except QueryError as x :
            print str(x)

        parts = query.split(",")
        for part in parts :
            if part :
                kv = part.split("=", 2)
                if len(kv) == 1 :
                    k, v = "tag", kv[0]
                else :
                    k, v = kv
                if k[0] == "<" :
                    k = k[1:]
                    sort.append((k,1))
                if k[0] == ">" :
                    k = k[1:]
                    sort.append((k,-1))
                search[k] = v.strip() #{ "$regex" : v, "$options" : 'i' }
        print search, sort
        the_blobs = list(blobs.Blob.find_by_tags(self.db, search, sort))
        self.render("search.html", the_blobs=the_blobs, query=query)

