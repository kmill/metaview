import tornado.ioloop
import tornado.web as web
import tornado.escape
import tornado.template
import tornado.httputil
import tornado.httpclient
import httplib

import pymongo
import gridfs
import gridfs.errors
import pymongo.json_util as json_util
import json

import uuid
import base64
import hashlib

import datetime
import time
import email.utils

import blobs
import blobviews
import bbviews
import docviews

def random256() :
    return base64.b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes)

PORTNUM = 8222

def json_encode(obj) :
    return json.dumps(obj, default=json_util.default)
def json_decode(s) :
    return json.loads(s, object_hook=json_util.object_hook)

class MVRequestHandler(tornado.web.RequestHandler) :
    @property
    def db(self) :
        return self.application.db
    @property
    def fs(self) :
        return self.application.fs
    @property
    def handler(self) :
        return self

    def write_error(self, status_code, **kwargs) :
        import traceback
        self.write("<html><title>%(code)d: %(message)s</title>" 
                    "<body><p>%(code)d: %(message)s</p>" % {
                "code": status_code,
                "message": httplib.responses[status_code],
                })
        if "exc_info" in kwargs:
            self.write("<pre>")
            for line in traceback.format_exception(*kwargs["exc_info"]):
                self.write(tornado.escape.xhtml_escape(line))
            self.write("</pre>")
        self.finish("</body></html>")

    def get_current_user(self) :
        username = self.get_secure_cookie("user")
        username = "kmill" # for debugging!
        if not username :
            return None
        res = list(self.db.users.find({"username" : username}))
        if not res :
            return None
        user = res[0]
        return user
    def get_user_blob_bases(self, username=None) :
        if not username :
            return [self.current_user["blob_base"]]
        else :
            res = list(self.db.users.find({"username" : username}))
            return [r["blob_base"] for r in res]

    def get_blob(self, blobid) :
        return blobs.Blob(self.db, blobid)
    def get_blob_url(self, blob, action="show") :
        return tornado.httputil.url_concat("/blob/%s" % blob.id,
                                           dict(action=action))
    def blob_link(self, blob, action, text=None) :
        if not text :
            text = action
        esc_url = tornado.escape.xhtml_escape(self.get_blob_url(blob, action))
        return "<a href=\"%s\">%s</a>" % (esc_url, text)

    def get_doc_url(self, doc_id, action="show") :
        return tornado.httputil.url_concat("/doc/%s" % doc_id,
                                           dict(action=action))
    def get_doc_link(self, doc_id, action, text=None) :
        if not text :
            text = action
        esc_url = tornado.escape.xhtml_escape(self.get_doc_url(doc_id, action))
        return "<a href=\"%s\">%s</a>" % (esc_url, text)

    def reply_to_blob_link(self, blob, text=None) :
        if not text :
            text = "reply"
        url = tornado.httputil.url_concat("/create/" + tornado.escape.xhtml_escape(blob["doc"]["blob_base"]),
                                          dict(reply_to=str(blob["doc"]["doc_id"])))
        return "<a href=\"%s\">%s</a>" % (url, text)
    def get_file_url(self, id) :
        return "/file/%s" % id

class MainHandler(MVRequestHandler) :
    @tornado.web.authenticated
    def get(self) :
        self.render("main_test.html",
                    the_blobs=blobs.Blob.find_by_tags(self.db, {"_reply_to" : None,
                                                                "_masked" : False}))

class DocHandler(MVRequestHandler) :
    def decode_from_id(self, id) :
        action = self.get_argument("action", "show")
        try :
            doc_id = uuid.UUID(id)
        except :
            raise tornado.web.HTTPError(404)
        return action, doc_id

    @tornado.web.authenticated
    def get(self, id) :
        action, doc_id = self.decode_from_id(id)
        docviews.doc_views[action](self, doc_id)


class BlobHandler(MVRequestHandler) :
    def decode_from_id(self, id) :
        action = self.get_argument("action", "show")
        this_blob = blobs.Blob(self.db, uuid.UUID(id))
        if "_id" not in this_blob["doc"] :
            raise tornado.web.HTTPError(404)
        return action, this_blob

    @tornado.web.authenticated
    def get(self, id) :
        action, this_blob = self.decode_from_id(id)
        self.render("blob_view.html", action=action, blob=this_blob)

    @tornado.web.authenticated
    def post(self, id) :
        action, this_blob = self.decode_from_id(id)
        blobviews.blob_views[action+"_post"](self, this_blob, {})

class CreateHandler(MVRequestHandler) :
    @tornado.web.authenticated
    def get(self, blob_base=None) :
        if not blob_base :
            blob_base = self.current_user["blob_base"]
        create_views = [(blob_type, blob_type == self.get_argument("type", ""),
                         blobviews.blob_create_view(self, blob_type, blob_base, {}))
                        for blob_type in blobs.blob_types]
        try :
            doc_id = uuid.UUID(self.get_argument("reply_to", ""))
            reply_tos = blobs.Blob.tags_to_blobs(self.db, self.db.tags.find({"_doc_id" : doc_id,
                                                                             "_masked" : False}))
        except ValueError :
            reply_tos = None
        self.render("create_views.html", create_views=create_views, reply_tos=reply_tos)
            
    @tornado.web.authenticated
    def post(self, blob_base=None) :
        blob = blobs.create_blob(self, {})
        self.redirect(self.get_blob_url(blob))

class SearchHandler(MVRequestHandler) :
    @tornado.web.authenticated
    def get(self, blob_base) :
        search = { "blob_base" : blob_base, "_masked" : False }
        sort = [("created", -1)]
        query = self.get_argument("q", "")
        parts = query.split(",")
        for part in parts :
            if part :
                kv = part.split("=", 2)
                if len(kv) == 1 :
                    k, v = "tag", kv[0]
                else :
                    k, v = kv
                if k[0] == "<" :
                    k = k[1:]
                    sort.append((k,1))
                if k[0] == ">" :
                    k = k[1:]
                    sort.append((k,-1))
                search[k] = v.strip() #{ "$regex" : v, "$options" : 'i' }
        print search, sort
        the_blobs = list(blobs.Blob.find_by_tags(self.db, search, sort))
        self.render("search.html", the_blobs=the_blobs, query=query)

class BlobBaseHandler(MVRequestHandler) :
    @tornado.web.authenticated
    def get(self, blob_base, view) :
        bbviews.bb_views[view](self, blob_base)

class LoginHandler(MVRequestHandler) :
    def prepare(self) :
        if self.current_user :
            self.redirect(self.get_argument("next", "/"))
    def get(self) :
        self.render("login.html",
                    next=self.get_argument("next", "/"),
                    err_msg=self.get_argument("err_msg", None))
    def post(self) :
        username = self.get_argument("username", "")
        md5password = hashlib.md5(self.get_argument("password", "")).hexdigest()
        if list(self.db.users.find({"username" : username, "password" : md5password})) :
            self.set_current_user(username)
            self.redirect(self.get_argument("next", "/"))
        else :
            url = tornado.httputil.url_concat(self.get_login_url(),
                                              dict(next=self.get_argument("next", "/"),
                                                   err_msg="Login failed."))
            self.redirect(url)
    def set_current_user(self, username) :
        if username :
            self.set_secure_cookie("user", username)
        else :
            self.clear_cookie("user")

class LogoutHandler(MVRequestHandler) :
    @tornado.web.authenticated
    def get(self) :
        self.clear_cookie("user")
        self.redirect("/")

class FileHandler(MVRequestHandler) :
    CACHE_MAX_AGE = 86400*365*10 #10 years

    @tornado.web.authenticated
    def head(self, path) :
        self.get(path, include_body=False)

    @tornado.web.authenticated
    def get(self, id, include_body=True) :
        try :
            f = self.fs.get(uuid.UUID(id))
            self.set_header("Content-Type", f.content_type)
            self.set_header("Content-Length", f.length)
            self.set_header("Last-Modified", f.upload_date)

            # aggressive caching
            self.set_header("Expires", (datetime.datetime.utcnow() +
            datetime.timedelta(seconds=self.CACHE_MAX_AGE)))
            self.set_header("Cache-Control", "max-age=" + str(self.CACHE_MAX_AGE))

            ims_value = self.request.headers.get("If-Modified-Since")
            if ims_value is not None :
                date_tuple = email.utils.parsedate(ims_value)
                if_since = datetime.datetime.fromtimestamp(time.mktime(date_tuple))
                if if_since >= f.upload_date :
                    self.set_status(304)
                    return
            
            if not include_body :
                return

            self.write(f.read())
            self.flush()
            print "wrote"
            return
        except (gridfs.errors.NoFile, ValueError) :
            raise tornado.web.HTTPError(404)

class RebuildHandler(MVRequestHandler) :
    @tornado.web.authenticated
    def get(self) :
        self.db.tags.remove()
        ids = self.db.doc.find({}, fields={"_id"})
        for idv in ids :
            id = idv["_id"]
            self.write("<p>%s</p>" % id)
            blob = blobs.Blob(self.db, id)
            blobs.mask_blob_metadata(blob)
            blobs.update_blob_metadata(blob)
        self.write("<p>Done.</p>")

class BlobModule(tornado.web.UIModule) :
    @property
    def db(self) :
        return self.handler.application.db
    @property
    def fs(self) :
        return self.handler.application.fs

    def render(self, blob, action, **data) :
        print "BlobModule; blob.id =",blob.id
        return blobviews.blob_views[action](self, blob, data.copy())

class SyncHandler(MVRequestHandler) :
    @tornado.web.authenticated
    def get(self) :
        last_server = self.current_user.get("last_sync_server", {})
        args = {"lblobbase" : self.get_argument("lblobbase", last_server.get("lblobbase", "")),
                "servername" : self.get_argument("servername", last_server.get("servername", "")),
                "rblobbase" : self.get_argument("rblobbase", last_server.get("rblobbase", "")),
                "username" : self.get_argument("username", last_server.get("username", "")),
                "has_password" : (not self.get_argument("errormsg", False)
                                  and last_server.get("password", False) and True),
                "errormsg" : self.get_argument("errormsg", None)}
        self.render("sync.html", **args)
    @tornado.web.asynchronous
    @tornado.web.authenticated
    def post(self) :
        last_server = self.current_user.get("last_sync_server", {})
        args = {"lblobbase" : self.get_argument("lblobbase", ""),
                "servername" : self.get_argument("servername", ""),
                "rblobbase" : self.get_argument("rblobbase", ""),
                "username" : self.get_argument("username", ""),
                "password" : self.get_argument("password", "")}
        if args["servername"] == last_server.get("servername", None) \
                and args["rblobbase"] == last_server.get("rblobbase", None) \
                and args["username"] == last_server.get("username", None) \
                and args["password"] in ["", "default"] :
            # this is a bug (what if password is "" or "default"? [but
            # it shouldn't])
            args["password"] = last_server.get("password", None)
        # bug: redirect involves password in plain text!
        if not args["lblobbase"] :
            url = tornado.httputil.url_concat("/sync",
                                              dict(errormsg="Missing local blob base",
                                                   **args))
            self.redirect(url)
            return
        if args["lblobbase"] not in self.get_user_blob_bases() :
            url = tornado.httputil.url_concat("/sync",
                                              dict(errormsg="That local blob base is not accessible.",
                                                   **args))
            self.redirect(url)
            return
        if not args["servername"] :
            url = tornado.httputil.url_concat("/sync",
                                              dict(errormsg="Missing server name",
                                                   **args))
            self.redirect(url)
            return
        if not args["rblobbase"] :
            url = tornado.httputil.url_concat("/sync",
                                              dict(errormsg="Missing remote blob base",
                                                   **args))
            self.redirect(url)
            return
        if not args["username"] :
            url = tornado.httputil.url_concat("/sync",
                                              dict(errormsg="Missing remote username",
                                                   **args))
            self.redirect(url)
            return

        self.db.users.update({"_id" : self.current_user["_id"]}, {"$set" : {"last_sync_server" : args }})

        if self.get_argument("synctype") == "push" :
            self.do_push(args)
        elif self.get_argument("synctype") == "pull" :
            self.do_pull(args)
        else :
            url = tornado.httputil.url_concat("/sync", args)
            self.redirect(url)

    def do_pull(self, args) :
        my_docids = list(d["_id"]
                         for d in self.db.doc.find({"blob_base" : args["lblobbase"]}, fields=["_id"]))
        my_fileids = list(f["_id"]
                          for f in self.db.fs.files.find({"blob_base" : args["lblobbase"]}, fields=["_id"]))
        to_send = {"synctype" : "pull",
                   "username" : args["username"],
                   "password" : args["password"],
                   "blob_base" : args["rblobbase"],
                   "my_docids" : my_docids,
                   "my_fileids" : my_fileids}

        request = tornado.httpclient.HTTPRequest("http://%s/syncprotocol" % args["servername"],
                                                 method="POST",
                                                 headers={"Content-Type" : "application/json"},
                                                 body=json_encode(to_send))
        http_client = tornado.httpclient.AsyncHTTPClient()
        http_client.fetch(request, callback=self.on_sync_response_pull(args, objects={"blobs":[], "files":[]}))

    def on_sync_response_pull(self, args, objects) :
        def _on_sync_response_pull(response) :
            if response.error :
                url = tornado.httputil.url_concat("/sync",
                                                  dict(errormsg="Exception: "+str(response.error),
                                                       **args))
                self.redirect(url)
                return
            data = json_decode(response.body)
            for doc in data["docs"] :
                doc["blob_base"] = args["lblobbase"]
                self.db.doc.insert(doc)
                blob = blobs.Blob(self.db, doc["_id"], doc=doc)
                blobs.mask_blob_metadata(blob)
                blobs.update_blob_metadata(blob)
                objects["blobs"].append(blob)
            self.do_file_pull(args, objects, data["files"], 0)
        return _on_sync_response_pull

    def do_file_pull(self, args, objects, files, i) :
        if i < len(files) :
            file = files[i]
            http_client = tornado.httpclient.AsyncHTTPClient()
            http_client.fetch("http://%s/file/%s" % (args["servername"], file["_id"]),
                              callback=self.on_file_pull(args, objects, files, i))
        else :
            objects["blobs"].sort(key=lambda x:x["created"])
            self.render("sync_successful.html", objects=objects, sync_type="pull")
            return

    def on_file_pull(self, args, objects, files, i) :
        def _on_file_pull(response) :
            if response.error :
                self.write("Exception on file %s: %s" % (file["_id"], response.error))
                response.rethrow()
                self.finish()
                return

            file = files[i]
            
            f = self.fs.new_file(_id=file["_id"],
                                 upload_date=file["uploadDate"],
                                 filename=file["filename"],
                                 content_type=file["contentType"],
                                 blob_base=args["lblobbase"])
            try :
                f.write(response.body)
            except Exception, x :
                self.write("Exception on file %s: %s" % (file["_id"], x))
                self.finish()
                return
            f.close()
            Objects["files"].append(file["_id"])

            self.do_file_pull(args, objects, files, i+1)
        return _on_file_pull

    def do_push(self, args) :
        my_docids = list(d["_id"]
                         for d in self.db.doc.find({"blob_base" : args["lblobbase"]}, fields=["_id"]))
        my_fileids = list(f["_id"]
                          for f in self.db.fs.files.find({"blob_base" : args["lblobbase"]}, fields=["_id"]))
        to_send = {"synctype" : "prepush",
                   "username" : args["username"],
                   "password" : args["password"],
                   "blob_base" : args["rblobbase"],
                   "my_docids" : my_docids,
                   "my_fileids" : my_fileids}

        request = tornado.httpclient.HTTPRequest("http://%s/syncprotocol" % args["servername"],
                                                 method="POST",
                                                 headers={"Content-Type" : "application/json"},
                                                 body=json_encode(to_send))
        http_client = tornado.httpclient.AsyncHTTPClient()
        http_client.fetch(request, callback=self.on_sync_response_push(args))

    def on_sync_response_push(self, args) :
        def _on_sync_response_push(response) :
            if response.error :
                url = tornado.httputil.url_concat("/sync",
                                                  dict(errormsg="Exception: "+str(response.error),
                                                       **args))
                self.redirect(url)
                return
            their_ids = json_decode(response.body)
            docs = list(self.db.doc.find({"blob_base" : args["lblobbase"],
                                          "_id" : {"$in" : their_ids["new_docids"]}}))
            files = list(self.db.fs.files.find({"blob_base" : args["lblobbase"],
                                                "_id" : {"$in" : their_ids["new_fileids"]}}))
            http_client = tornado.httpclient.AsyncHTTPClient()
            if docs :
                to_send = {"synctype" : "pushdocs",
                           "username" : args["username"],
                           "password" : args["password"],
                           "blob_base" : args["rblobbase"],
                           "docs" : docs}
                request = tornado.httpclient.HTTPRequest("http://%s/syncprotocol" % args["servername"],
                                                         method="POST",
                                                         headers={"Content-Type" : "application/json"},
                                                         body=json_encode(to_send))
                http_client.fetch(request, callback=self.on_docs_pushed(args, docs, files))
            else :
                self.do_push_files(args, {"blobs" : [], "files" : []}, files, 0)
        return _on_sync_response_push

    def on_docs_pushed(self, args, docs, files) :
        def _on_docs_pushed(response) :
            if response.error :
                self.write("Exception when pushing docs: %s" % response.error)
                response.rethrow()
                self.finish()
                return
            self.do_push_files(args, {"blobs" : list(blobs.Blob(self.db, d["_id"], doc=d) for d in docs),
                                      "files" : []},
                               files, 0)
        return _on_docs_pushed

    def do_push_files(self, args, objects, files, i) :
        if i < len(files) :
            file = files[i]

            to_send = {"synctype" : "pushfile",
                       "username" : args["username"],
                       "password" : args["password"],
                       "blob_base" : args["rblobbase"],
                       "file" : file,
                       "file_contents" : base64.b64encode(self.fs.get(file["_id"]).read())}

            request = tornado.httpclient.HTTPRequest("http://%s/syncprotocol" % args["servername"],
                                                     method="POST",
                                                     headers={"Content-Type" : "application/json"},
                                                     body=json_encode(to_send))

            http_client = tornado.httpclient.AsyncHTTPClient()
            http_client.fetch(request, callback=self.on_file_pushed(args, objects, files, i))
        else :
            objects["blobs"].sort(key=lambda x:x["created"])
            self.render("sync_successful.html", objects=objects, sync_type="push")
            return
    def on_file_pushed(self, args, objects, files, i) :
        def _on_file_pushed(response) :
            file = files[i]
            if response.error :
                self.write("Exception when pushing file %s: %s" % (["_id"], response.error))
                response.rethrow()
                self.finish()
                return
            objects["files"].append(file)
            self.do_push_files(args, objects, files, i+1)
        return _on_file_pushed


class SyncProtocolHandler(MVRequestHandler) :
    def check_xsrf_cookie(self) :
        """Override"""
        pass
    def post(self) :
        args = json_decode(self.request.body)

        username = args.get("username", "")
        password = str(hashlib.md5(args.get("password", "")).hexdigest())
        blob_base = args.get("blob_base", "")

        res = list(self.db.users.find({"username" : username, "password" : password}))
        if not res :
            raise tornado.web.HTTPError(403)
        if blob_base not in self.get_user_blob_bases(username=username) :
            raise tornado.web.HTTPError(403)
        
        if args["synctype"] == "pull" :
            docs = list(self.db.doc.find({"blob_base" : blob_base,
                                          "_id" : {"$nin" : args["my_docids"]}}))
            files = list(self.db.fs.files.find({"blob_base" : blob_base,
                                                "_id" : {"$nin" : args["my_fileids"]}}))
            response = {"docs" : docs,
                        "files" : files}
            self.write(json_encode(response))
            return
        elif args["synctype"] == "prepush" :
            their_docids = args["my_docids"]
            their_fileids = args["my_fileids"]
            my_docids = set(d["_id"]
                            for d in self.db.doc.find({"blob_base" : args["blob_base"]}, fields=["_id"]))
            my_fileids = set(f["_id"]
                             for f in self.db.fs.files.find({"blob_base" : args["blob_base"]}, fields=["_id"]))
            their_new_docids = [d for d in their_docids if d not in my_docids]
            their_new_fileids = [f for f in their_fileids if f not in my_fileids]
            response = {"new_docids" : their_new_docids,
                        "new_fileids" : their_new_fileids}
            self.finish(json_encode(response))
            return
        elif args["synctype"] == "pushdocs" :
            for doc in args["docs"] :
                doc["blob_base"] = args["blob_base"]
                self.db.doc.insert(doc)
                blob = blobs.Blob(self.db, doc["_id"], doc=doc)
                blobs.mask_blob_metadata(blob)
                blobs.update_blob_metadata(blob)
        elif args["synctype"] == "pushfile" :
            file = args["file"]
            f = self.fs.new_file(_id=file["_id"],
                                 upload_date=file["uploadDate"],
                                 filename=file["filename"],
                                 content_type=file["contentType"],
                                 blob_base=args["blob_base"])
            try :
                f.write(base64.b64decode(args["file_contents"]))
            except Exception, x :
                f.close()
                raise tornado.web.HTTPError(500, "Error with writing file to database")
            f.close()
        else :
            raise tornado.web.HTTPError(405)
        

class MVApplication(tornado.web.Application) :
    def __init__(self) :
        self.db = pymongo.Connection()['metaview']
        self.db.users.ensure_index("username", unique=True)
        self.fs = gridfs.GridFS(self.db, collection='fs')

        settings = dict(
            app_title="MetaView",
            template_path="templates",
            static_path="static",
            login_url="/login",
            cookie_secret=random256(),
            ui_modules={"BlobModule" : BlobModule},
            xsrf_cookies=True,
            )
        
        handlers = [
            (r"/", MainHandler),
            (r"/file/(.*)", FileHandler),
            (r"/doc/(.*)", DocHandler),
            (r"/blob/(.*)", BlobHandler),
            (r"/create", CreateHandler),
            (r"/create/(.*)", CreateHandler),
            (r"/search/(.*)", SearchHandler),
            (r"/bb/(\w*)/(.*)", BlobBaseHandler),
            (r"/login", LoginHandler),
            (r"/logout", LogoutHandler),
            (r"/sync", SyncHandler),
            (r"/syncprotocol", SyncProtocolHandler),
            (r"/rebuild", RebuildHandler),
            ]
        
        tornado.web.Application.__init__(self, handlers, **settings)

#
# Initialized modules
#
import modtext
import modfile

if __name__=="__main__" :
    print "Starting metaview..."
    application = MVApplication()
    application.listen(PORTNUM)
    print "Listening on port",PORTNUM
    tornado.ioloop.IOLoop.instance().start()
