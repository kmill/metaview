# blobs.py
# January 2012, Kyle Miller
#
# A blob is some representation of a document.  Importantly, blobs are
# versioned.

import uuid
import datetime
import re
from actionlist import ContinueWith, DeferAction, ActionList, action_assert, ActionTable
from tornado.httpclient import HTTPError

##
## Blob container object
##

class Blob(object) :
    """This is an object which pulls in data lazily from the given database."""
    def __init__(self, db, id, **kwargs) :
        """shouldn't call directly"""
        self.db = db
        self.id = id
        self._data = kwargs.copy()

    @staticmethod
    def find_by_tags(db, spec, sort=None) :
        if sort :
            return (Blob(db, res["_id"], tags=res) for res in db["tags"].find(spec).sort(sort))
        else :
            return (Blob(db, res["_id"], tags=res) for res in db["tags"].find(spec).sort([("created", -1)]))

    def get_data(self, type) :
        """Gets an entry from the "type" collection whose _id is
        self.id.  Caches the result."""
        if type not in self._data :
            res = self.db[type].find_one(self.id)
            self._data[type] = res or dict()
        return self._data[type]
    def __getitem__(self, key) :
        return self.get_data(key)

##
## Model for blobs
##
create_blob = ActionList(doc="Provides a way to create a blob from form data.")
update_blob = ActionList(doc="Provides a way to update a blob from an edited blob object.")
delete_blob = ActionList(doc="Provides a way to delete a blob a blob object.")
remove_blob_metadata = ActionList(doc="Removes traces of the previous version of the blob's metadata.")
update_blob_metadata = ActionList(doc="Adds the metadata for the blob.")

# each mod{blobtype} should register themselves in this array for the
# create view to be able to populate itself with create views
blob_types = []

#
# create_blob
#

@create_blob.add_action
def create_blob_default(request_handler, doc) :
    blob_base = request_handler.get_argument("blob_base", request_handler.current_user["blob_base"])
    comment = request_handler.get_argument("comment", "")
    db = request_handler.db
    blob_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    doc.update({"_id" : blob_id, # the unique id of this entry
                "deleted" : False,
                "doc_id" : doc_id, # the id of the new document
                "blob_base" : blob_base,
                "previous_version" : None, # it's not a new version of anything
                "reply_to" : None, # and not in reply to anything
                "created" : datetime.datetime.now(),
                "comment" : comment,
                })
    db['doc'].insert(doc)
    blob = Blob(db, id=blob_id, doc=doc)
    update_blob_metadata(blob)
    return blob

#
# update_blob
#

@update_blob.add_action
def update_blob_default(blob) :
    newblob_id = uuid.uuid4()
    oldblob_id = blob.id
    blob.id = newblob_id
    blob["doc"].update({"_id" : newblob_id,
                        "previous_version" : oldblob_id,
                        "created" : datetime.datetime.now(), # update when this blob was created
                        })
    blob.db["doc"].insert(blob["doc"])
    remove_blob_metadata(blob)
    update_blob_metadata(blob)
    return blob

#
# delete_blob
#

@delete_blob.add_action
def delete_blob_default(blob) :
    newblob_id = uuid.uuid4()
    oldblob_id = blob.id
    blob.id = newblob_id
    blob["doc"].update({"_id" : newblob_id,
                        "deleted" : True,
                        "previous_version" : oldblob_id,
                        "created" : datetime.datetime.now(), # update when this blob was created (deleted)
                        "comment" : "**deleted**",
                        })
    blob.db["doc"].insert(blob["doc"])
    remove_blob_metadata(blob)
    return blob

#
# remove_blob
#

@remove_blob_metadata.add_action
def remove_blob_metadata_tag(blob) :
    if blob["previous_version"] is not None :
        blob.db["tags"].remove(blob["doc"]["previous_version"])
    blob.db["tags"].remove(blob.id)
    raise DeferAction()

#
# update_blob
#

@update_blob_metadata.add_action
def update_blob_metadata_default(blob) :
    blob["tags"].update({"_id" : blob.id,
                         "_doc_id" : blob["doc"]["doc_id"],
                         "created" : blob["doc"]["created"],
                         "blob_base" : blob["doc"]["blob_base"],
                         })
    blob.db["tags"].update({"_id" : blob.id}, blob["tags"], upsert=True)
