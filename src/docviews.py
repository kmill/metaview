# docviews.py
# January 2011, Kyle Miller

import blobs
from actionlist import ContinueWith, DeferAction, ActionList, action_assert, ActionTable
from tornado.httpclient import HTTPError
import uuid
import blobviews

#
# Definitions of view handlers
#

doc_views = ActionTable(doc="""These are views for documents.""")

doc_views.define_actionlist("show", doc="For showing a whole document.")

@doc_views.add_action("show")
def doc_view_show_default(handler, doc_id) :
    entries = handler.db.tags.find({"_doc_id" : doc_id}).sort([("created", -1)])
    the_blobs = list(blobs.Blob.tags_to_blobs(handler.db, entries))
    if not the_blobs :
        raise HTTPError(404)
    handler.write(handler.render_string("doc_view.html",
                                        the_blobs=the_blobs,
                                        replies=render_blob_replies(handler, the_blobs[0])))

def render_blob_replies(handler, blob) :
    res = list(handler.db.tags.find({"_reply_to" : blob["doc"]["doc_id"]}).sort([("created", 1)]))
    if not res :
        return ""
    else :
        out = "\n".join(blobviews.blob_to_html(handler.render_string, b, {"suppress_reply_to_data" : True })
                        + render_blob_replies(handler, b) for b in blobs.Blob.tags_to_blobs(handler.db, res))
        return "<div class=\"blob_reply\">%s</div>" % out
