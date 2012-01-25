# modtext.py
# January 2011, Kyle Miller

import blobs
import views
from actionlist import ContinueWith, DeferAction, ActionList, action_assert, ActionTable
from tornado.httpclient import HTTPError
import uuid
import markup

#
# adding a "text" blob type
#
blobs.blob_types.append("text")

###
### Model for text blobs
###

#
# handler for modifying text blobs
#

@blobs.update_blob_metadata.add_action
def update_markup_blob_metadata(blob) :
    """Adds the tags in the text of a text blob to the tags table in
    the blob."""
    action_assert(blob["doc"]["type"] == "text")
    
    tags, html = markup.parse_markup(blob["doc"]["text_content"])
    new_tags = dict()
    for key,values in tags.iteritems() :
        if type(values) == list :
            new_tags[key] = [value.lower() for value in values]
        else :
            new_tags[key] = values.lower()
    blob["tags"].update(new_tags)
    raise DeferAction()

#
# handler for creating text blobs (closely associated with create view)
#

@blobs.create_blob.add_action
def create_blob_default(request, doc) :
    action_assert(request.get_argument("blob_type", "") == "text")
    doc["type"] = "text"
    doc["text_content"] = request.get_argument("text_content")
    raise DeferAction()


###
### Views
###

#
# blob_to_html
#

@views.blob_to_html.add_action
def markup_blob_to_html(render_string, blob, a_data) :
    action_assert(blob["doc"]["type"] == "text")
    tags, html = markup.parse_markup(blob["doc"]["text_content"])
    a_data["content"] = a_data.get("content", "")+html
    raise DeferAction()

#
# action: edit
#

@views.blob_views.add_action("edit")
def edit_markup_blob(request, blob, a_data) :
    action_assert(blob["doc"]["type"] == "text")
    a_data["content"] = request.render_string("textblob_edit.html",
                                              prior_content=a_data.get("content", ""),
                                              text=blob["doc"]["text_content"])
    raise DeferAction()

#
# action: edit_post
#

@views.blob_views.add_action("edit_post")
def edit_markup_blob(request, blob, a_data) :
    action_assert(request.get_argument("blob_type", "") == "text")
    blob["doc"]["type"] = "text"
    blob["doc"]["text_content"] = request.get_argument("text_content")
    raise DeferAction()

#
# text blob create view
#

@views.blob_create_view.add_action
def blob_create_view_text(request, blob_type, blob_base, a_data) :
    if blob_type != "text" :
        raise DeferAction()
    prior_content = a_data.get("content", "")
    a_data["content"] = request.render_string("textblob_edit.html",
                                              prior_content=prior_content,
                                              text_content="")
    raise DeferAction()
