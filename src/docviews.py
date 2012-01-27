# docviews.py
# January 2011, Kyle Miller

import blobs
from actionlist import ContinueWith, DeferAction, ActionList, action_assert, ActionTable
from tornado.httpclient import HTTPError
import uuid
import blobviews

#
# Definitions of view handlers
#

doc_views = ActionTable(doc="""These are views for documents.""")

doc_views.define_actionlist("show", doc="For showing a whole document (and all of its current versions).")
doc_views.define_actionlist("history", doc="For showing the history of a document.")

#
# doc action: show
#

@doc_views.add_action("show")
def docview_show_default(handler, doc_id) :
    entries = handler.db.tags.find({"_doc_id" : doc_id, "_masked" : False}).sort([("created", -1)])
    the_blobs = list(blobs.Blob.tags_to_blobs(handler.db, entries))
    if not the_blobs :
        raise HTTPError(404)
    handler.write(handler.render_string("doc_view.html",
                                        the_blobs=the_blobs,
                                        replies=render_blob_replies(handler, the_blobs[0])))

def render_blob_replies(handler, blob) :
    res = list(handler.db.tags.find({"_reply_to" : blob["doc"]["doc_id"],
                                     "_masked" : False}).sort([("created", 1)]))
    if not res :
        return ""
    else :
        out = "\n".join(blobviews.blob_to_html(handler.render_string, b, {"suppress_reply_to_data" : True })
                        + render_blob_replies(handler, b) for b in blobs.Blob.tags_to_blobs(handler.db, res))
        return "<div class=\"blob_reply\">%s</div>" % out

#
# doc action: history
#

@doc_views.add_action("history")
def docview_history_default(handler, doc_id) :
    entries = handler.db.doc.find({"doc_id" : doc_id}).sort([("created", 1)])
    blob_by_id = dict()
    # ([seen_versions], curr_version)
    version_data = []
    prev_ref = []
    last_vd = ([], None, [])
    for blob in blobs.Blob.docs_to_blobs(handler.db, entries) :
        blob_by_id[blob.id] = blob
        
        prev = blob["doc"].get("previous_version", None) or None
        prev_ref.append(prev)
        if prev and prev in last_vd[0] :
            i = last_vd[0].index(prev)
            last_vd = (last_vd[0][:i+1] + [blob.id] + last_vd[0][i+1:], blob.id)
            version_data.append(last_vd)
        else :
            last_vd = (last_vd[0]+[blob.id], blob.id)
            version_data.append(last_vd)

    history_entries = []

    last_trails = []
    for i, (seen, curr) in enumerate(version_data) :
        will_use = prev_ref[i+1:]
        curr_trails = [s for s in seen if s in will_use or s == curr]

        meta_last_trails = dict()
        for t in curr_trails :
            meta_last_trails.setdefault(t,[]).append(t)
            prev = blob_by_id[t]["doc"].get("previous_version", None) or None
            if t not in last_trails :
                meta_last_trails.setdefault(prev,[]).append(t)
        # invariant: each list in meta_last_trails is in increasing order of date.

        dests = []
        for lt in last_trails :
            if lt in meta_last_trails :
                dests.append(tuple([curr_trails.index(t) for t in meta_last_trails[lt]]))
            else :
                dests.append(())
        # invariant: flattening dests yields 0..len(curr_trails) in increasing order.
        
        if dests :
            change_lines = make_change_string(dests, len(curr_trails))
            history_entries.append((change_lines.replace(" ", "&nbsp;"), None))

        last_trails = curr_trails

        line = ""
        for b in curr_trails :
            if b == curr :
                line += "* "
            else :
                line += "| "
        history_entries.append((line, blob_by_id[curr]))
    handler.render("doc_history.html", history_entries=history_entries)


def make_change_string(dests, num_dest) :
    lines = []
    #print "dests",dests
    we_want = zip(range(num_dest))
    while dests != we_want :
        change_line = []
        new_dests = [()]*max(num_dest, len(dests))
        for i in xrange(len(dests)) :
            item = dests[i]
            format = [" ", " ", ""]
            for d in item :
                if d == i :
                    format[1] = "|"
                    new_dests[i] += (d,)
                elif d < i :
                    format[0] = "/"
                    new_dests[i-1] += (d,)
                elif d > i :
                    format[2] = "\\"
                    new_dests[i+1] += (d,)
            change_line.append(format)
        while new_dests and new_dests[-1] == () :
            del new_dests[-1]
        make_line = []
        for i in xrange(len(change_line)) :
            next_inter = " " if i >= len(change_line) - 1 else change_line[i+1][0]
            make_line.append(change_line[i][1] + (change_line[i][2] or next_inter))
        lines.append("".join(make_line))
        dests = new_dests
        #print dests
    return "\n".join(lines)

#print make_change_string([(0,1)], 2)
