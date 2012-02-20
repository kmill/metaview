# blobviews.py
# January 2011, Kyle Miller

import blobs
from actionlist import ContinueWith, DeferAction, ActionList, action_assert, ActionTable
from tornado.httpclient import HTTPError
import uuid

#
# Definitions of view handlers
#

blob_views = ActionTable(doc="""These are views for individual blobs.
  The signature for each is (handler, blob, a_data) -> String""")

blob_views.define_actionlist("show", doc="For rendering the blob to html.")
blob_views.define_actionlist("edit", doc="For a blob edit view.")
blob_views.define_actionlist("edit_post", doc="For posting from a blob edit view.")
blob_views.define_actionlist("delete", doc="For a deleting a blob.")
blob_views.define_actionlist("delete_post", doc="For actually deleting a blob.")

blob_to_html = ActionList(doc="""This is to convert a blob to html.
  It is used by the show blob_view.  It's separated so we can make a
  BlobModule for blobs""")

blob_get_name = ActionList(doc="""This is to get a string identifier
   of a blob for a user to view.  Not guaranteed to be unique!""")

blob_create_view = ActionList(doc="""This is to construct a view for
   creating a new blob.  This isn't a blob_view since we don't know
   the blob yet.""")

#
# blob_get_name
#

@blob_get_name.add_action
def blob_get_name_default(blob, default=None) :
    if default :
        return default
    else :
        return str(blob["doc"]["doc_id"])

#
# blob_to_html
#

@blob_to_html.add_action
def blob_to_html_default(render_string, blob, a_data) :
    has_replies = 0 < len(list(blob.db.tags.find({"_reply_to" : blob["doc"]["doc_id"],
                                                  "_masked" : False}, fields=["_id"])))
    d = {"blob_id" : blob.id,
         "doc_id" : blob["doc"]["doc_id"],
         "created" : blob["doc"]["created"].strftime("%a, %b %e %Y, %l:%M:%S %p"), #%b %d %Y %I:%M:%S %p"),
         "content" : a_data.get("content", "<center><p><em>Unknown blob type!</em></p></center>"),
         "blob" : blob,
         "has_replies" : has_replies,
         "a_data" : a_data,
         }
    return render_string("blob.html", **d)

#
# action: show
#

@blob_views.add_action("show")
def show_blob_default(handler, blob, a_data) :
    full_view = a_data.get("full_view", False)
    if full_view :
        return render_blob_replies(handler, blob, top=True)
    else :
        return blob_to_html(handler.render_string, blob, a_data)

def render_blob_replies(handler, blob, top=False) :
    res = list(handler.db.tags.find({"_reply_to" : blob["doc"]["doc_id"],
                                     "_masked" : False}).sort([("created", 1)]))
    if not res :
        suffix = ""
    else :
        suffix = "\n".join(render_blob_replies(handler, b) for b in blobs.Blob.tags_to_blobs(handler.db, res))
    return "%s\n<div class=\"blob_reply\">%s</div>" % \
        (blob_to_html(handler.render_string, blob, {"suppress_has_reply" : True,
                                                    "suppress_reply_to_data" : not top}),
         suffix)

#
# action: edit
#

@blob_views.add_action("edit")
def edit_blob_default(handler, blob, a_data) :
    hidden = {"blob_id" : str(blob.id)}
    content = a_data.get("content", "")
    return handler.render_string("blob_edit.html",
                                 blob=blob,
                                 hidden=hidden,
                                 content=content)

#
# action: edit_post
#

@blob_views.add_action("edit_post")
def edit_post_blob_default(handler, blob, a_data) :
    if handler.get_argument("blob_id", "") != str(blob.id) :
        raise HTTPError(405)
    blob["doc"]["comment"] = handler.get_argument("comment", "")
    blob = blobs.update_blob(handler.get_user_identifier(long=True), blob)
    handler.redirect(handler.get_blob_url(blob))
    return "<p>Saved.</p>"

#
# action: delete
#

@blob_views.add_action("delete")
def delete_blob_default(handler, blob, a_data) :
    return handler.render_string("blob_delete.html",
                                 blob=blob)

#
# action: delete_post
#

@blob_views.add_action("delete_post")
def delete_blob_default(handler, blob, a_data) :
    if handler.get_argument("blob_id", "") != str(blob.id) :
        raise HTTPError(405)
    blob2 = blobs.delete_blob(handler.get_user_identifier(long=True), blob)
    handler.render("blob_deleted.html", blob=blob, blob2=blob2)


#
# default blob create view
#

@blob_create_view.add_action
def blob_create_view_default(handler, blob_type, blob_base, a_data) :
    try :
        reply_to = uuid.UUID(handler.get_argument("reply_to", ""))
    except ValueError :
        reply_to = None
    content = a_data.get("content", "")
    return handler.render_string("blob_create.html",
                                 blob_base=blob_base,
                                 reply_to=reply_to,
                                 content=content)

