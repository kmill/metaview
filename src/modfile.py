# modfile.py
# January 2011, Kyle Miller

import blobs
import blobviews
from blobviews import blob_views
from actionlist import ContinueWith, DeferAction, ActionList, action_assert, ActionTable
from tornado.httpclient import HTTPError
import uuid
import markup

from modtext import get_prepared_tags_for_db

#
# adding a "file" blob type
#
blobs.blob_types.append("file")

###
### Model for text blobs
###

#
# handler for modifying text blobs
#

@blobs.update_blob_metadata.add_action
def update_fileblob_metadata(blob) :
    """Adds the tags in the text of a text blob to the tags table in
    the blob."""
    action_assert(blob["doc"]["type"] == "file")

    blob["tags"].update(get_prepared_tags_for_db(blob["doc"]["text_content"]))
    blob["tags"].update({"filename" : blob["doc"]["file_name"]})
    raise DeferAction()

#
# handler for creating text blobs (closely associated with create view)
#

@blobs.create_blob.add_action
def create_fileblob(handler, doc) :
    action_assert(handler.get_argument("blob_type", "") == "file")
    doc["type"] = "file"
    ok = put_file_into_db(handler, handler.request.files.get("file_filename", []), doc)
    if not ok :
        # if the new file blob doesn't have a file, then we just make
        # it into a text blob
        doc["type"] = "text"
    doc["text_content"] = handler.get_argument("text_content")
    raise DeferAction()

def put_file_into_db(handler, form_input, doc) :
    if form_input :
        file_id = uuid.uuid4()
        file_data = form_input[0]
        file_name = file_data.get("filename", None)
        file_type = file_data.get("content_type", "text/plain")
        f = handler.fs.new_file(_id=file_id,
                                filename=file_name,
                                content_type=file_type)
        try :
            f.write(file_data["body"])
        except Exception :
            f.close()
            raise
        f.close()
        doc.update({"file_id" : file_id,
                    "file_name" : file_name,
                    "file_type" : file_type})
        return True
    else :
        return False

###
### Views
###

#
# blob_to_html
#

@blobviews.blob_to_html.add_action
def fileblob_to_html(render_string, blob, a_data) :
    action_assert(blob["doc"]["type"] == "file")
    tags, tag_html, html = markup.parse_markup(blob["doc"]["text_content"])
    a_data["content"] = render_string("fileblob.html",
                                      blob=blob,
                                      prior_content=a_data.get("content", ""),
                                      content=tag_html+html)
    raise DeferAction()

#
# action: edit
#

@blob_views.add_action("edit")
def edit_fileblob(handler, blob, a_data) :
    action_assert(blob["doc"]["type"] == "file")
    a_data["content"] = handler.render_string("fileblob_edit.html",
                                              prior_content=a_data.get("content", ""),
                                              text_content=blob["doc"]["text_content"])
    raise DeferAction()

#
# action: edit_post
#

@blob_views.add_action("edit_post")
def edit_fileblob(handler, blob, a_data) :
    action_assert(handler.get_argument("blob_type", "") == "file")
    blob["doc"]["type"] = "file"
    # put_file_into_db may or may not succeed, but that is immaterial
    # since the failure mode is inheriting the file data from the
    # previous version
    put_file_into_db(handler, handler.request.files.get("file_filename", []), blob["doc"])
    blob["doc"]["text_content"] = handler.get_argument("text_content")
    raise DeferAction()

#
# text blob create view
#

@blobviews.blob_create_view.add_action
def blob_create_view_text(handler, blob_type, blob_base, a_data) :
    action_assert(blob_type == "file")

    prior_content = a_data.get("content", "")
    a_data["content"] = handler.render_string("fileblob_edit.html",
                                              prior_content=prior_content,
                                              text_content="")
    raise DeferAction()
