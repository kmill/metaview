# bbviews.py
# January 2011, Kyle Miller
#
# views of a blob base

import blobs
from actionlist import ContinueWith, DeferAction, ActionList, action_assert, ActionTable
from tornado.httpclient import HTTPError
import uuid

#
# Definitions of view handlers
#

bb_views = ActionTable(doc="""These are views for entire blob bases.""")

bb_views.define_actionlist("recent_changes", doc="For showing what's recently been done to a blob.")

@bb_views.add_action("recent_changes")
def bb_views_recent_changes(handler, blob_base) :
    entries = handler.db.doc.find({"blob_base" : blob_base}).sort([("modified", -1)])
    the_blobs = blobs.Blob.docs_to_blobs(handler.db, entries)
    handler.render("bbrecent_changes.html", blob_base=blob_base, the_blobs=the_blobs)
