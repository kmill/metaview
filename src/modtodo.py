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

import datetime

import modtext

date_fields = ["date", "deadline"]


@blobviews.blob_get_name.add_action
def blob_get_name_todo(blob, default=None) :
    tags = blob["tags"]
    if tags and "todo" in tags :
        return "@todo " + (tags["todo"][0] if type(tags["todo"]) is list else tags["todo"])
    raise DeferAction()

@blobs.filter_blob_metadata.add_action
def filter_blob_metadata_dates(db, tags) :
    if "todo" not in tags :
        raise DeferAction()
    else :
        for field in date_fields :
            if field in tags :
                date = tags[field][0] if type(tags[field]) is list else tags[field]
                try :
                    date = fuzzydate.parse_date(date, tags["created"])
                except fuzzydate.DateFormatException as x :
                    date = "%s (DateFormatException: %r)" % (date, x.args)
                tags[field] = date

        raise ContinueWith(db, tags)

def nice_date_format(date) :
    if date.hour == date.minute == date.second == 0 :
        return date.strftime("%a, %b %e %Y")
    elif date.minute == date.second == 0 :
        return date.strftime("%a, %b %e %Y, %l %p")
    elif date.second == 0 :
        return date.strftime("%a, %b %e %Y, %l:%M %p")
    else :
        return date.strftime("%a, %b %e %Y, %l:%M:%S %p")

@modtext.format_tag_value.add_action
def format_tag_value_date_fields(blob, key, values) :
    if not values or not blob["tags"] or "todo" not in blob["tags"] :
        raise DeferAction()
    else :
        tags = blob["tags"]
        if key in date_fields and key in tags :
            v = tags[key][0] if type(tags[key]) is list else tags[key]
            if type(v) is datetime.datetime :
                return True, [nice_date_format(v)]
            else :
                return True, [v]
        else :
            raise DeferAction()
