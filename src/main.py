import blobs
import views
import tornado.ioloop
import tornado.web as web
import tornado.escape
import tornado.template
import tornado.httputil
import pymongo
import uuid
import base64
import hashlib
import httplib

def random256() :
    return base64.b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes)

PORTNUM = 8222

class MVRequestHandler(tornado.web.RequestHandler) :
    @property
    def db(self) :
        return self.application.db

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

    def get_blob_url(self, blob, action="show") :
        return tornado.httputil.url_concat("/blob/%s" % blob.id,
                                           dict(action=action))
    def blob_link(self, blob, action, text=None) :
        if not text :
            text = action
        esc_url = tornado.escape.xhtml_escape(self.get_blob_url(blob, action))
        return "<a href=\"%s\">%s</a>" % (esc_url, text)

class MainHandler(MVRequestHandler) :
    @tornado.web.authenticated
    def get(self) :
        self.render("main_test.html", the_blobs=blobs.Blob.find_by_tags(self.db, {}))

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
        views.blob_views[action+"_post"](self, this_blob, {})

class CreateHandler(MVRequestHandler) :
    @tornado.web.authenticated
    def get(self, blob_base=None) :
        if not blob_base :
            blob_base = self.current_user["blob_base"]
        create_views = [(blob_type,
                         views.blob_create_view(self, blob_type, blob_base, {}))
                        for blob_type in blobs.blob_types]
        self.render("create_views.html", create_views=create_views)
    @tornado.web.authenticated
    def post(self, blob_base=None) :
        blob = blobs.create_blob(self, {})
        self.redirect(self.get_blob_url(blob))

class SearchHandler(MVRequestHandler) :
    @tornado.web.authenticated
    def get(self, blob_base) :
        search = { "blob_base" : blob_base }
        sort = [("created", -1)]
        query = self.get_argument("q", "")
        parts = query.split(",")
        for part in parts :
            if part :
                kv = part.split("=", 2)
                if len(kv) == 1 :
                    k, v = "category", kv[0]
                else :
                    k, v = kv
                if k[0] == "<" :
                    k = k[1:]
                    sort.append((k,1))
                if k[0] == ">" :
                    k = k[1:]
                    sort.append((k,-1))
                search[k] = v.strip().lower() #{ "$regex" : v, "$options" : 'i' }
        print search, sort
        the_blobs = list(blobs.Blob.find_by_tags(self.db, search, sort))
        self.render("search.html", the_blobs=the_blobs, query=query)

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

class RebuildHandler(MVRequestHandler) :
    @tornado.web.authenticated
    def get(self) :
        for blob in blobs.Blob.find_by_tags(self.db, {}) :
            self.write("<p>%s</p>" % blob.id)
            blobs.update_blob_metadata(blob)
        self.write("<p>Done.</p>")

class BlobModule(tornado.web.UIModule) :
    def render(self, blob, action) :
        return views.blob_views[action](self, blob, {})
        #return views.blob_to_html(self.render_string, blob, {})

class MVApplication(tornado.web.Application) :
    def __init__(self) :
        self.db = pymongo.Connection()['metaview']
        self.db.users.ensure_index("username", unique=True)

        settings = dict(
            app_title="MetaView",
            template_path="../templates",
            static_path="../static",
            login_url="/login",
            cookie_secret=random256(),
            ui_modules={"BlobModule" : BlobModule},
            xsrf_cookies=True,
            )
        
        handlers = [
            (r"/", MainHandler),
            (r"/blob/(.*)", BlobHandler),
            (r"/create", CreateHandler),
            (r"/create/(.*)", CreateHandler),
            (r"/search/(.*)", SearchHandler),
            (r"/login", LoginHandler),
            (r"/logout", LogoutHandler),
            (r"/rebuild", RebuildHandler),
            ]
        
        tornado.web.Application.__init__(self, handlers, **settings)

#
# Initialized modules
#
import modtext

if __name__=="__main__" :
    print "Starting metaview..."
    application = MVApplication()
    application.listen(PORTNUM)
    print "Listening on port",PORTNUM
    tornado.ioloop.IOLoop.instance().start()
