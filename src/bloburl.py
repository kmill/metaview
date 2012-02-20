import tornado.httputil
import tornado.escape

def get_blob_url(blob, action="show") :
    return tornado.httputil.url_concat("/blob/%s" % blob.id,
                                       dict(action=action))
def blob_link(blob, action, text=None) :
    if not text :
        text = action
    esc_url = tornado.escape.xhtml_escape(get_blob_url(blob, action))
    return "<a href=\"%s\">%s</a>" % (esc_url, text)
