# modtodo.py
# Feb 2012, Kyle Miller
# support for todo entries

import blobs
import blobviews
from blobviews import blob_views, blob_to_html, blob_create_view
from actionlist import ContinueWith, DeferAction, ActionList, action_assert, ActionTable
from tornado.httpclient import HTTPError
import uuid
import markup

import fuzzydate
from nicedate import nice_date_format

import datetime

import modtext

# date_field, reckon_from, create_if_not_exists
todo_date_fields = [("reckon_from", "modified", "created"),
                    ("deadline","reckon_from", False),
                    ("date","reckon_from", False)]
event_date_fields = [("reckon_from", "modified", "created"),
                     ("date", "created", False),
                     ("until", "date", False)]

# todo

@blobviews.blob_get_name.add_action
def blob_get_name_todo(blob, default=None) :
    tags = blob["tags"]
    if tags and "todo" in tags :
        return "@todo " + (tags["todo"][0] if type(tags["todo"]) is list else tags["todo"])
    raise DeferAction()

def list_lift(l) :
    if type(l) is list : return l
    return [l]
def list_drop(l) :
    if type(l) is list and len(l) == 1 :
        return l[0]
    return l

@blobs.filter_blob_metadata.add_action
def filter_blob_metadata_dates(db, tags) :
    if "todo" not in tags :
        raise DeferAction()
    else :
        tags["tag"] = list_drop(list_lift(tags.get("tag", [])) + ["todo"])
        for field, depends, createp in todo_date_fields :
            if depends in tags and type(tags[depends]) is datetime.datetime :
                if field in tags :
                    sdate = tags[field][0] if type(tags[field]) is list else tags[field]
                    try :
                        date = fuzzydate.parse_date(sdate, tags[depends])
                    except fuzzydate.DateFormatException as x :
                        date = "%s (DateFormatException: %r)" % (date, x.args)
                    tags[field] = date
                elif createp in tags and type(tags[createp]) is datetime.datetime :
                    tags[field] = tags[createp]

        raise ContinueWith(db, tags)

@modtext.format_tag_value.add_action
def format_tag_value_date_fields(blob, key, values) :
    if not values or not blob["tags"] or "todo" not in blob["tags"] :
        raise DeferAction()
    else :
        tags = blob["tags"]
        if key in (r[0] for r in todo_date_fields) and key in tags :
            v = tags[key][0] if type(tags[key]) is list else tags[key]
            if type(v) is datetime.datetime :
                return True, [nice_date_format(v)]
            else :
                return True, [v]
        else :
            raise DeferAction()


# events

@blobviews.blob_get_name.add_action
def blob_get_name_event(blob, default=None) :
    tags = blob["tags"]
    if tags and "event" in tags :
        return "@event " + (tags["event"][0] if type(tags["event"]) is list else tags["event"])
    raise DeferAction()

@blobs.filter_blob_metadata.add_action
def filter_blob_metadata_dates(db, tags) :
    if "event" not in tags :
        raise DeferAction()
    else :
        tags["tag"] = list_drop(list_lift(tags.get("tag", [])) + ["event"])
        for field, depends, createp in event_date_fields :
            if depends in tags and type(tags[depends]) is datetime.datetime :
                if field in tags :
                    sdate = tags[field][0] if type(tags[field]) is list else tags[field]
                    try :
                        date = fuzzydate.parse_date(sdate, tags[depends])
                    except fuzzydate.DateFormatException as x :
                        date = "%s (DateFormatException: %r)" % (date, x.args)
                    tags[field] = date
                elif createp in tags and type(tags[createp]) is datetime.datetime :
                    tags[field] = tags[createp]
                    
        raise ContinueWith(db, tags)

@modtext.format_tag_value.add_action
def format_tag_value_date_fields(blob, key, values) :
    if not values or not blob["tags"] or "event" not in blob["tags"] :
        raise DeferAction()
    else :
        tags = blob["tags"]
        if key in (d[0] for d in event_date_fields) and key in tags :
            v = tags[key][0] if type(tags[key]) is list else tags[key]
            if type(v) is datetime.datetime :
                return True, [nice_date_format(v)]
            else :
                return True, [v]
        else :
            raise DeferAction()
