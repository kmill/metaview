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
        assert type(id) != dict
        self.db = db
        self.id = id
        self._data = kwargs.copy()

    @staticmethod
    def ids_to_blobs(db, ids) :
        return (Blob(db, id) for id in ids)
    @staticmethod
    def docs_to_blobs(db, docs) :
        return (Blob(db, doc["_id"], doc=doc) for doc in docs)
    @staticmethod
    def tags_to_blobs(db, tagss) :
        return (Blob(db, tags["_id"], tags=tags) for tags in tagss)

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
    def invalidate(self, type) :
        if type in self._data :
            del self._data[type]

##
## Model for blobs
##
create_blob = ActionList(doc="Provides a way to create a blob from form data.")
update_blob = ActionList(doc="Provides a way to update a blob from an edited blob object.")
delete_blob = ActionList(doc="Provides a way to delete a blob a blob object.")
mask_blob_metadata = ActionList(doc="Mask traces of the previous version of the blob's metadata.")
update_blob_metadata = ActionList(doc="Adds the metadata for the blob.")

filter_blob_metadata = ActionList(doc="""Lets one filter the tags for
   a blob before they're stored into the database.""")

# each mod{blobtype} should register themselves in this array for the
# create view to be able to populate itself with create views
blob_types = []

#
# create_blob
#

@create_blob.add_action
def create_blob_default(handler, doc) :
    blob_base = handler.get_argument("blob_base", handler.current_user["blob_base"])
    comment = handler.get_argument("comment", "")
    db = handler.db
    blob_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    try :
        reply_to = uuid.UUID(handler.get_argument("reply_to", ""))
    except ValueError :
        reply_to = None
    doc.update({"_id" : blob_id, # the unique id of this entry
                "deleted" : False,
                "doc_id" : doc_id, # the id of the new document
                "blob_base" : blob_base,
                "previous_version" : None, # it's not a new version of anything
                "reply_to" : reply_to, # and not in reply to anything
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
    mask_blob_metadata(blob)
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
    new_doc = {"_id" : newblob_id,
               "doc_id" : blob["doc"]["doc_id"],
               "blob_base" : blob["doc"]["blob_base"],
               "deleted" : True,
               "previous_version" : oldblob_id,
               "reply_to" : blob["doc"]["reply_to"],
               "created" : datetime.datetime.now(), # that is, when the blob was deleted.
               "comment" : "**deleted**",
               "type" : None,
               }
    blob["doc"].clear()
    blob["doc"].update(new_doc)
    blob.db["doc"].insert(blob["doc"])
    mask_blob_metadata(blob)
    return blob

#
# remove_blob
#

@mask_blob_metadata.add_action
def mask_blob_metadata_tag(blob) :
    if blob["doc"]["previous_version"] is not None :
        blob.db.tags.update({"_id" : blob["doc"]["previous_version"]},
                            {"$set" : {"_masked" : True}}, upsert=True)
    raise DeferAction()

#
# update_blob
#

@update_blob_metadata.add_action
def update_blob_metadata_default(blob) :
    blob["tags"].update({"_id" : blob.id,
                         "_doc_id" : blob["doc"]["doc_id"],
                         "_reply_to" : blob["doc"].get("reply_to", None),
                         "created" : blob["doc"]["created"],
                         "blob_base" : blob["doc"]["blob_base"],
                         })
    if "_masked" not in blob["tags"] :
        blob["tags"]["_masked"] = False
    if not blob["doc"].get("deleted", False) :
        tags = filter_blob_metadata(blob.db, blob["tags"].copy())
        blob.db["tags"].update({"_id" : blob.id}, tags, upsert=True)
        blob.invalidate("tags")

#
# filter_blob_metadata
#

@filter_blob_metadata.add_action
def filter_blob_metadata_default(db, tags) :
    return tags

@filter_blob_metadata.add_action
def filter_blob_metadata_break_tag(db, tags) :
    if "tag" not in tags :
        raise DeferAction()
    else :
        if type(tags["tag"]) is list :
            tags["tag"] = [t.strip() for tl in tags["tag"] for t in tl.split(";")]
        else :
            tags["tag"] = [t.strip() for t in tags["tag"].split(";")]
        raise ContinueWith(db, tags)
