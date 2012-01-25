# views.py
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

blob_create_view = ActionList(doc="""This is to construct a view for
   creating a new blob.  This isn't a blob_view since we don't know
   the blob yet.""")

#
# blob_to_html
#

@blob_to_html.add_action
def blob_to_html_default(render_string, blob, a_data) :
    d = {"blob_id" : blob.id,
         "doc_id" : blob["doc"]["doc_id"],
         "created" : blob["doc"]["created"].strftime("%b %d %Y %I:%M:%S %p"),
         "content" : a_data.get("content", "<center><p><em>Unknown blob type!</em></p></center>"),
         "blob" : blob,
         }
    return render_string("blob.html", **d)

#
# action: show
#

@blob_views.add_action("show")
def show_blob_default(request, blob, a_data) :
    return blob_to_html(request.render_string, blob, a_data)

#
# action: edit
#

@blob_views.add_action("edit")
def edit_blob_default(request, blob, a_data) :
    hidden = {"blob_id" : str(blob.id)}
    content = a_data.get("content", "")
    return request.render_string("blob_edit.html",
                                 blob=blob,
                                 hidden=hidden,
                                 content=content)

#
# action: edit_post
#

@blob_views.add_action("edit_post")
def edit_post_blob_default(request, blob, a_data) :
    if request.get_argument("blob_id", "") != str(blob.id) :
        raise HTTPError(405)
    blob["doc"]["comment"] = request.get_argument("comment", "")
    blob = blobs.update_blob(blob)
    request.redirect(request.get_blob_url(blob))
    return "<p>Saved.</p>"

#
# action: delete
#

@blob_views.add_action("delete")
def delete_blob_default(request, blob, a_data) :
    return request.render_string("blob_delete.html",
                                 blob=blob)

#
# action: delete_post
#

@blob_views.add_action("delete_post")
def delete_blob_default(request, blob, a_data) :
    if request.get_argument("blob_id", "") != str(blob.id) :
        raise HTTPError(405)
    blob2 = blobs.delete_blob(blob)
    request.render("blob_deleted.html", blob=blob, blob2=blob2)


#
# default blob create view
#

@blob_create_view.add_action
def blob_create_view_default(request, blob_type, blob_base, a_data) :
    content = a_data.get("content", "")
    return request.render_string("blob_create.html",
                                 blob_base=blob_base,
                                 content=content)

