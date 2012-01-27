import tornado.ioloop
import tornado.web as web
import tornado.escape
import tornado.template
import tornado.httputil
import httplib

import pymongo
import gridfs
import gridfs.errors

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
        print blob.id
        return blobviews.blob_views[action](self, blob, data.copy())

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
