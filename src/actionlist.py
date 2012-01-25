# actionlist.py
# January 2012, Kyle Miller

class ContinueWith(Exception) :
    def __init__(self, *args, **kwargs) :
        self.args = args
        self.kwargs = kwargs
    def __repr__(self) :
        return "ContinueWith(*%r,**%r)" % (self.args, self.kwargs)

class DeferAction(Exception) :
    pass

class ActionList(object) :
    def __init__(self, doc=None) :
        self.actions = []
        self.doc = doc
    def run(self, args, kwargs) :
        for action in self.actions :
            try :
                return action(*args, **kwargs)
            except ContinueWith as x :
                args, kwargs = x.args, x.kwargs
            except DeferAction :
                pass
        return None
    def __call__(self, *args, **kwargs) :
        return self.run(args, kwargs)
    def add_action(self, f) :
        self.actions.insert(0, f)
        return f

def action_assert(bool) :
    if not bool :
        raise DeferAction()

class ActionTable(object) :
    def __init__(self, doc=None) :
        self.table = dict()
        self.doc = doc
    def define_actionlist(self, name, doc=None) :
        self.table[name] = ActionList(doc=doc)
    def add_action(self, table_name) :
        def _add_action(f) :
            return self.table[table_name].add_action(f)
        return _add_action
    def __getitem__(self, name) :
        return self.table[name]

if __name__=="__main__" :
    al = ActionList()
    
    @al.add_action
    def base_action(doc) :
        return doc
    @al.add_action
    def text_action(doc) :
        action_assert(doc["type"] == "text")
        doc.update({"tag" : "tagged"})
        raise ContinueWith(doc)

    print al.run({"type" : "image"})
    print al.run({"type" : "text"})
