# fuzzydate.py
# feb 2012 kylemiller
# for dealing with fuzzy date input

from mparserlib.lexer import *
import re
import datetime

lexer = Lexer([
        Spec(None,  r'[ \t\r\n,]+'), # whitespace (note comma!)
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

class DateFormatException(Exception) :
    pass

def parse_tokens(toks) :
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
            elif value > 12 :
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
        else :
            raise DateFormatException("Unknown",kind,value)
    return data

def eval_data(data, currdate) :
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
    if "year" in data :
        year = data["year"]
        if year < 100 : # 99 probably means 1999
            year += 1900
        valid.update({"day" : False, "hour" : False, "minute" : False, "second" : False})
        invalid.update({"month" : True, "day" : True,
                        "hour" : True, "minute" : True, "second" : True})
    if "month" in data :
        month = data["month"]
        if year is None : # take the year of the next coming month
            if month >= currdate.month :
                year = currdate.year
            else :
                year = currdate.year + 1
        valid.update({"day" : True, "hour" : False, "minute" : False, "second" : False})
        invalid.update({"day" : True, "hour" : True, "minute" : True, "second" : True})
    if "day" in data :
        if not valid["day"] : raise DateFormatException("day specificity requires a month")
        day = data["day"]
        if month is None :
            # day cannot be valid unless both haven't been set.
            year = currdate.year
            month = currdate.month
        valid.update({"hour" : True, "minute" : False, "second" : False})
        invalid.update({"hour" : True, "minute" : True, "second" : True})
    if "weekday" in data :
        if not valid["day"] : raise DateFormatException("weekday specificity requires a month")
        if month is not None and day is None :
            raise DateFormatException("weekday specificity cannot only have a month")
        nextdate = currdate + datetime.timedelta(days=(data["weekday"]+7-(currdate.weekday()+1))%6)
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
    return eval_data(parse_tokens(lexer.tokenize(s)), currdate)

while True :
    t = raw_input("> ")
    print parse_date(t, datetime.datetime.today())
