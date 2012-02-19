# modtext.py
# January 2011, Kyle Miller

import blobs
import blobviews
from blobviews import blob_views, blob_to_html, blob_create_view
from actionlist import ContinueWith, DeferAction, ActionList, action_assert, ActionTable
from tornado.httpclient import HTTPError
import uuid
import markup

format_tag_value = ActionList(doc="""Lets one format the value of a
   tag appropriately when rendering the page.""")


#
# adding a "text" blob type
#
blobs.blob_types.append("text")

def get_prepared_tags_for_db(text) :
    tags, tag_data, html = markup.parse_markup(text)
    new_tags = dict()
    for key,values in tags.iteritems() :
        if type(values) == list :
            #new_tags[key] = [value.lower() for value in values]
            new_tags[key] = [value for value in values]
        else :
            #new_tags[key] = values.lower()
            new_tags[key] = values
    return new_tags

###
### Model for text blobs
###

#
# handler for modifying text blobs
#

@blobs.update_blob_metadata.add_action
def update_textblob_metadata(blob) :
    """Adds the tags in the text of a text blob to the tags table in
    the blob."""
    action_assert(blob["doc"]["type"] == "text")
    
    blob["tags"].update(get_prepared_tags_for_db(blob["doc"]["text_content"]))
    raise DeferAction()

#
# handler for creating text blobs (closely associated with create view)
#

@blobs.create_blob.add_action
def create_textblob(handler, doc) :
    action_assert(handler.get_argument("blob_type", "") == "text")
    doc["type"] = "text"
    doc["text_content"] = handler.get_argument("text_content")
    raise DeferAction()


###
### Views
###

#
# blob_to_html
#

@blob_to_html.add_action
def textblob_to_html(render_string, blob, a_data) :
    action_assert(blob["doc"]["type"] == "text")
    tags, tag_data, html = markup.parse_markup(blob["doc"]["text_content"])
    a_data["content"] = a_data.get("content", "")+markup.parse_tags(format_tag_value, blob, *tag_data)+html
    raise DeferAction()

#
# blob_get_name
#

@blobviews.blob_get_name.add_action
def blob_get_name_default(blob, default=None) :
    tags = blob["tags"]
    if tags and "title" in tags :
        return "@title " + (tags["title"][0] if type(tags["title"]) is list else tags["title"])
    raise DeferAction()

#
# action: edit
#

@blob_views.add_action("edit")
def edit_textblob(handler, blob, a_data) :
    action_assert(blob["doc"]["type"] == "text")
    a_data["content"] = handler.render_string("textblob_edit.html",
                                              prior_content=a_data.get("content", ""),
                                              text_content=blob["doc"]["text_content"])
    raise DeferAction()

#
# action: edit_post
#

@blob_views.add_action("edit_post")
def edit_textblob(handler, blob, a_data) :
    action_assert(handler.get_argument("blob_type", "") == "text")
    blob["doc"]["type"] = "text"
    blob["doc"]["text_content"] = handler.get_argument("text_content")
    raise DeferAction()

#
# text blob create view
#

@blob_create_view.add_action
def create_view_textblob(handler, blob_type, blob_base, a_data) :
    if blob_type != "text" :
        raise DeferAction()
    prior_content = a_data.get("content", "")
    a_data["content"] = handler.render_string("textblob_edit.html",
                                              prior_content=prior_content,
                                              text_content="")
    raise DeferAction()


###
### Tags
###

@format_tag_value.add_action
def format_tag_value_default(blob, key, values) :
    return True, values
