import blobviews
import querylang
from nicedate import nice_date_format
import datetime
import bloburl

renderers = {}

def add_renderer(name) :
    def _add_renderer(f) :
        renderers[name] = f
        return f
    return _add_renderer

def my_str(o) :
    if type(o) is datetime.datetime :
        return nice_date_format(o)
    elif type(o) in (str, unicode) :
        return o
    elif type(o) is list :
        return u"[%s]" % ", ".join(my_str(o2) for o2 in o)
    else :
        return unicode(o)


@add_renderer("table")
def r_table(glob, *columns) :
    def _r_table(blobs) :
        out = ["<table class=\"qtable\"><tr><td></td>"]
        for c in columns :
            out.append("<th>%s</th>" % c)
        out.append("</tr>\n")
        for blob in blobs :
            out.append("<tr>")
            out.append("<td class=\"qtableshow\">%s</td>" \
                           % bloburl.blob_link(blob, "show", "(show)"))
            for c in columns :
                out.append(u"<td>%s</td>" % my_str(blob["tags"].get(c, "&nbsp;")))
            out.append("</tr>\n")
        out.append("</table>")
        return "".join(out)
    return _r_table
