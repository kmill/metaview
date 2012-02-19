# fuzzydate.py
# feb 2012 kylemiller
# for dealing with fuzzy date input

__all__ = ["parse_date", "DateFormatException"]

from mparserlib.lexer import *
import re
import datetime

lexer = Lexer([
        Spec(None,  r'[\s,]+'), # whitespace (note comma!)
        Spec(None, r'today|now'), # remove since blank string means today
        Spec("relative", r'(last|next)\s+[A-Za-z]+', re.IGNORECASE),
        Spec("hms", r'\d+:\d+:\d+'),
        Spec("hm", r'\d+:\d+'),
        Spec("mdy", r'\d+/\d+/\d+'),
        Spec("md", r'\d+/\d+'),
        Spec("mdy", r'\d+-\d+-\d+'),
        Spec("md", r'\d+-\d+'),
        Spec("hmeridian", r'\d+(am|pm)', re.IGNORECASE),
        Spec("meridian", r'am|pm', re.IGNORECASE),
        Spec("num", r"\d+(st|nd|rd|th)?"),
        Spec("text", r"[A-Za-z]+"),
        ])

month_map = [
    ("jan", 1),
    ("feb", 2),
    ("mar", 3),
    ("apr", 4),
    ("may", 5),
    ("jun", 6),
    ("jul", 7),
    ("aug", 8),
    ("sep", 9),
    ("oct", 10),
    ("nov", 11),
    ("dec", 12)
    ]

week_map = [
    ("su", 0),
    ("mo", 1),
    ("tu", 2),
    ("we", 3),
    ("th", 4),
    ("fr", 5),
    ("sa", 6),
    ]
week_map2 = [
    ("m", 1),
    ("t", 2),
    ("w", 3),
    ("h", 4),
    ("f", 5),
    ]

#relative_words = [
#    ("yesterday", ("day", -1)),
#    ("tomorrow", ("day", 1)),

class DateFormatException(Exception) :
    pass

def parse_tokens(toks, currdate) :
    """Interprets the tokens to find what data we know about the date.
    The resulting dictionary is fed into eval_data."""
    numcycle = ["day", "hour"]
    data = {}
    def try_append(data, stuff) :
        for k,v in stuff :
            if k in data :
                raise DateFormatException("Replicated key",k)
            data[k] = v
    def _int(v) :
        return int(v.rstrip("stndrdth"))
    for tok in toks :
        kind = tok.kind
        value = tok.value
        if kind=="hms" :
            try_append(data,
                       zip(["hour", "minute", "second"],
                           map(int, value.split(":"))))
        elif kind=="hm" :
            try_append(data,
                       zip(["hour", "minute"],
                           map(int, value.split(":"))))
        elif kind=="mdy" :
            try :
                vals = map(int, value.split("/"))
            except ValueError :
                vals = map(int, value.split("-"))
            try_append(data,
                       zip(["month", "day", "year"], vals))
        elif kind=="md" :
            try :
                vals = map(int, value.split("/"))
            except ValueError :
                vals = map(int, value.split("-"))
            keys = ["month", "day"]
            if vals[1] > 31 :
                keys[1] = "year"
            try_append(data, zip(keys, vals))
        elif kind=="num" :
            try :
                value = int(value)
            except ValueError :
                value = _int(value)
                try_append(data, [("day", value)])
                continue
            if value > 31 :
                try_append(data, [("year", value)])
            elif value > 24 :
                try_append(data, [("day", value)])
            elif "day" not in data :
                try_append(data, [("day", value)])
            elif "hour" not in data :
                try_append(data, [("hour", value)])
            else :
                raise DateFormatException("Unknown kind of number in date", value)
        elif kind=="hmeridian" :
            value = value.lower()
            try_append(data, [("hour", int(value[:-2])),
                              ("meridian", value[-2:]),
                              ("minute", 0),
                              ("second", 0)])
        elif kind=="meridian" :
            value = value.lower()
            try_append(data, [("meridian", value)])
        elif kind=="text" :
            value = value.lower()
            if value=="yesterday" :
                try_append(data, [("deltaday", -1)])
                continue
            if value=="tomorrow" :
                try_append(data, [("deltaday", 1)])
                continue
            for m,n in month_map :
                if value.startswith(m) :
                    try_append(data, [("month", n)])
                    break
            else :
                for d,n in week_map :
                    if value.startswith(d) :
                        try_append(data, [("weekday", n)])
                        break
                else :
                    for d,n in week_map2 :
                        if value == d :
                            try_append(data, [("weekday", n)])
                            break
                    else :
                        raise DateFormatException("Unknown text", value)
        elif kind=="relative" :
            m = re.match(r"(last|next)\s+(.*)", value.lower())
            direction = -1 if m.group(1) == "last" else 1
            w = m.group(2)
            if w == "week" :
                try_append(data, [("deltaweek", direction)])
                continue
            elif w == "month" :
                try_append(data, [("deltamonth", direction)])
                continue
            elif w == "year" :
                try_append(data, [("deltayear", direction)])
                continue
            for m,n in month_map :
                if w.startswith(m) :
                    try_append(data, [("month", n)])
                    if direction == 1 :
                        if n <= currdate.month :
                            try_append(data, [("year", currdate.year+1)])
                        else :
                            try_append(data, [("year", currdate.year)])
                    elif direction == -1 :
                        if n >= currdate.month :
                            try_append(data, [("year", currdate.year-1)])
                        else :
                            try_append(data, [("year", currdate.year)])                    
                    break
            else :
                for d,n in week_map :
                    if w.startswith(d) :
                        try_append(data, [("weekday", n - (7 if direction == -1 else -7))])
                        break
                else :
                    for d,n in week_map2 :
                        if w == d :
                            try_append(data, [("weekday", n - (7 if direction == -1 else -7))])
                            break
                    else :
                        raise DateFormatException("Unknown relative", value)
        else :
            raise DateFormatException("Unknown",kind,value)
    return data

def eval_data(data, currdate) :
    """Takes the result of parse_token and figures out the date."""
    print data
    year = None
    month = None
    day = None
    hour = None
    minute = None
    second = None
    # valid for input next
    valid = {"year" : True, "month" : True, "day" : True,
             "hour" : True, "minute" : True, "second" : True}
    # invalid for using currdate as the default value
    invalid = {"year" : False, "month" : False, "day" : False,
               "hour" : False, "minute" : False, "second" : False}
    if "deltayear" in data :
        year = currdate.year + data["deltayear"]
    if "year" in data :
        if year is not None and year != data["year"] :
            raise DateFormatException("year conflicts with year delta")
        year = data["year"]
        if year < 100 : # 99 probably means 1999
            year += 1900
        valid.update({"day" : False, "hour" : False, "minute" : False, "second" : False})
        invalid.update({"month" : True, "day" : True,
                        "hour" : True, "minute" : True, "second" : True})
    if "deltamonth" in data :
        if year is not None :
            raise DateFormatException("cannot use month delta with a year")
        month = currdate.month + data["deltamonth"]
        year = currdate.year
        if month > 12 :
            month -= 12
            year += 1
        elif month < 1 :
            month += 12
            year -= 1
        valid.update({"day" : True, "hour" : False, "minute" : False, "second" : False})
        invalid.update({"hour" : True, "minute" : True, "second" : True})
    if "month" in data :
        if month is not None and month != data["month"] :
            raise DateFormatException("month conflicts with month delta")
        month = data["month"]
        if year is None : # take the year of the next coming month
            if month >= currdate.month :
                year = currdate.year
            else :
                year = currdate.year + 1
        valid.update({"day" : True, "hour" : False, "minute" : False, "second" : False})
        invalid.update({"day" : True, "hour" : True, "minute" : True, "second" : True})
    if "deltaday" in data :
        if month is None :
            month = currdate.month
        if year is None :
            year = currdate.year
        nextdate = datetime.datetime(year, month, currdate.day) \
            + datetime.timedelta(days=data["deltaday"])
        year = nextdate.year # rational: "yesterday last month" shold be allowed
        month = nextdate.month
        day = nextdate.day
        valid.update({"hour" : True, "minute" : False, "second" : False})
        invalid.update({"hour" : True, "minute" : True, "second" : True})
    if "day" in data :
        if not valid["day"] : raise DateFormatException("day specificity requires a month")
        day = data["day"]
        if month is None :
            # day cannot be valid unless both haven't been set.
            year = currdate.year
            month = currdate.month
            if day < currdate.day : # get next month's version
                month += 1
                if month > 12 :
                    month = 1
                    year += 1
        valid.update({"hour" : True, "minute" : False, "second" : False})
        invalid.update({"hour" : True, "minute" : True, "second" : True})
    if "weekday" in data :
        if not valid["day"] : raise DateFormatException("weekday specificity requires a month")
        if month is not None and day is None :
            raise DateFormatException("weekday specificity cannot only have a month")
        if data["weekday"] < 0 :
            dd = (data["weekday"]+7-(currdate.weekday()+1)%7)%7 - 7
        elif data["weekday"] >= 7 : # not this week, but _next_ week
            dd = (data["weekday"]%7+7-(currdate.weekday()+1)%7)%7 + 7
        else :
            dd = (data["weekday"]+7-(currdate.weekday()+1)%7)%7
        nextdate = currdate + datetime.timedelta(days=dd)
        if year is not None and year != nextdate.year :
            raise DateFormatException("weekday conficts with year")
        year = nextdate.year
        if month is not None and month != nextdate.month :
            raise DateFormatException("weekday conficts with month")
        month = nextdate.month
        if day is not None and day != nextdate.day :
            raise DateFormatException("weekday conficts with day number")
        day = nextdate.day
        valid.update({"hour" : True, "minute" : False, "second" : False})
        invalid.update({"hour" : True, "minute" : True, "second" : True})
    if "deltaweek" in data :
        if day is None :
            day = currdate.day
        if month is None :
            month = currdate.month
        if year is None :
            year = currdate.year
        nextdate = datetime.datetime(year,month,day) + datetime.timedelta(days=7*data["deltaweek"])
        day, month, year = nextdate.day, nextdate.month, nextdate.year
        valid.update({"hour" : True, "minute" : False, "second" : False})
        invalid.update({"hour" : True, "minute" : True, "second" : True})
    if "hour" in data :
        if not valid["hour"] : raise DateFormatException("hour specificity requires a day")
        hour = data["hour"]
        if "meridian" in data :
            if hour > 12 and data["meridian"] == "am" :
                raise DateFormatException("24-hour time conflicts with 'am'")
            if hour < 12 and data["meridian"] == "pm" :
                hour += 12
        valid.update({"minute" : True, "second" : False})
        invalid.update({"minute" : True, "second" : True})
    if "minute" in data :
        if not valid["minute"] : raise DateFormatException("minute specificity requires an hour")
        minute = data["minute"]
        valid.update({"second" : True})
        invalid.update({"second" : True})
    if "second" in data :
        second = data["second"]
    
    if year is None : year = currdate.year
    if month is None :
        if invalid["month"] :
            month = 1
        else :
            month = currdate.month
    if day is None :
        if invalid["day"] :
            day = 1
        else :
            day = currdate.day
    if hour is None :
        if invalid["hour"] :
            hour = 0
        else :
            hour = currdate.hour
    if minute is None :
        if invalid["minute"] :
            minute = 0
        else :
            minute = currdate.minute
    if second is None :
        if invalid["second"] :
            second = 0
        else :
            second = currdate.second
    return datetime.datetime(year, month, day, hour, minute, second, tzinfo=currdate.tzinfo)

def parse_date(s, currdate) :
    """Takes a string and a datetime from which to reckon a new
    datetime.  Strings can be like the following:
    
    * saturday 5:00pm

    * 3rd january

    * 2 -> gives the second of the month.

    * 2 11 -> gives 11am of the second of the next month.

    * 2am

    * 2 feburary 2012 10:22pm

    Errors in the input raise a DateFormatException with a
    semi-explanation."""
    return eval_data(parse_tokens(lexer.tokenize(s), currdate), currdate)


if __name__=="__main__" :
    while True :
        t = raw_input("> ")
        print parse_date(t, datetime.datetime.today())
