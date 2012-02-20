import blobviews
import querylang
from nicedate import nice_date_format, nice_time_format
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

@add_renderer("list")
def r_list(glob) :
    def _r_list(blobs) :
        out = ["<ul>"]
        for b in blobs :
            out.append("<li>%s %s</li>\n" \
                           % (bloburl.blob_link(b, "show", "(show)"),
                              b["tags"]["_name"]))
        out.append("</ul>")
        return "".join(out)
    return _r_list

@add_renderer("calendar")
def r_calendar(glob, *date_columns) :
    def _r_calendar(blobs) :
        data = []
        for b in blobs :
            tags = b["tags"]
            for dc in date_columns :
                if dc in tags and type(tags[dc]) == datetime.datetime :
                    data.append((tags[dc], b))
                    break
        data.sort(key=lambda x : x[0])

        if not data :
            start = end = datetime.datetime.now()
        else :
            start = data[0][0]
            end = data[-1][0]
        start = start+datetime.timedelta(days=-(start.isoweekday()%7))
        start = datetime.datetime(start.year, start.month, start.day)
        end = end+datetime.timedelta(days=(6-end.isoweekday())%7)
        end = datetime.datetime(end.year, end.month, end.day)

        weeks = ((end-start).days+1)/7

        days = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]

        now = datetime.datetime.now()

        j = 0
        out = ["<table class=\"rcalendar\">\n<tr>"]
        for i in xrange(7) :
            out.append("<th>%s</th>" % days[i])
        out.append("</tr>\n")
        for w in xrange(weeks) :
            out.append("<tr>")
            for d in xrange(7) :
                date = start + datetime.timedelta(days=7*w+d)
                is_today = now.year==date.year and now.month==date.month and now.day==date.day
                out.append("<td %s><div class=\"rcalendardate\">%s</div>" \
                               % ("class=\"rcalendardatetoday\"" if is_today else "",
                                  date.strftime("%b %e")))
                while j < len(data) :
                    edate = data[j][0]
                    if date.year == edate.year \
                            and date.month == edate.month \
                            and date.day == edate.day :
                        out.append("<div class=\"rcalendarentry\">%s %s</div>\n"
                                   % (
                                nice_time_format(edate),
                                bloburl.blob_link(data[j][1], "show",
                                                  data[j][1]["tags"]["_name"])))
                        j += 1
                    else :
                        break
                out.append("</td>\n")
            out.append("</tr>\n")
        out.append("</table>")
        return "".join(out)
    return _r_calendar
