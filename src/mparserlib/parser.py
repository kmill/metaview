# parser.py
# Feb 2012, Kyle Miller

import itertools

__all__ = ["ParserError", "FwdDecl", "a", "between", "constp", "emptyp", "eof",
           "many", "many1", "satisfy", "sepby", "sepby1", "skip"]

class ParserError(Exception) :
    def __init__(self, i, pos, unexpected, expecting) :
        self.i = i
        self.pos = pos
        self.unexpected = unexpected
        self.expecting = expecting
    @classmethod
    def makeError(cls, input, i, expecting=[]) :
        if i < len(input) :
            unexpected = input[i]
            pos = unexpected.pos
        else :
            unexpected = "end of input"
            pos = None
        return cls(i, pos, unexpected, expecting)
    def addExpectations(self, expts) :
        self.expecting = TList(expts, self.expecting)
        return self
    def setExpectations(self, expts) :
        self.expecting = expts
        return self
    def ateSomething(self, i) :
        if self.i is None :
            return i != None
        else :
            return self.i != i
    def __str__(self) :
        i, pos, unexpected, expecting = self.i, self.pos, self.unexpected, self.expecting
        expts = []
        for e in expecting :
            if e not in expts :
                expts.append(e)
        if pos :
            posdesc = "line %r, column %r.\n" % pos
        else :
            posdesc = ""
        expt = ""
        if len(expts) == 1 :
            expt = "\nExpecting %s." % expts[0]
        elif len(expts) > 1 :
            expt = "\nExpecting %s or %s." % ((", ".join(str(e) for e in expts[:-1]), expts[-1]))
        return "".join([posdesc,
                        "Unexpected %s." % unexpected,
                        expt])

class _Tuple(object) :
    def __init__(self, iterable) :
        self.contents = tuple(iterable)
    @staticmethod
    def concat(ts) :
        ts = [t for t in ts if t is not None]
        if ts :
            if len(ts) == 1 :
                return ts[0]
            lifted = [t if type(t)==_Tuple else _Tuple([t]) for t in ts]
            return reduce(lambda x,y : x+y, lifted)
        else :
            return None
        
    def __add__(self, other) :
        if other == None :
            return self
        return _Tuple(itertools.chain(self.contents, other))
    def __radd__(self, other) :
        if other == None :
            return self
        return _Tuple(itertools.chain(other, self.contents))
    def __iter__(self) :
        for x in self.contents :
            yield x
    def __repr__(self) :
        return "_Tuple(%r)" % (self.contents,)

class TList(object) :
    def __init__(self, left, right) :
        self.left = left
        self.right = right
    def __iter__(self) :
        for x in self.left :
            yield x
        for x in self.right :
            yield x

class Parser(object) :
    def parse(self, input) :
        i, res = self._parse(list(input), 0)
        return res
    def expectsMsg(self, msg) :
        return _ReExpectParser(self, msg)
    def __add__(self, other) :
        if not isinstance(other, Parser) :
            raise TypeError("can only add parsers")
        return _ConcatParser(self, other)
    def __mul__(self, other) :
        if not isinstance(other, Parser) :
            raise TypeError("can only multiply parsers")
        return _ApParser(self, other)
    def __or__(self, other) :
        if not isinstance(other, Parser) :
            raise TypeError("can only 'or' parsers")
        return _EitherParser(self, other)
    def __rshift__(self, f) :
        return _FMapParser(self, f)
    def __ge__(self, f) :
        return _BindParser(self, f)

class _FMapParser(Parser) :
    """Parser(a) -> (a -> b) -> Parser(b)"""
    def __init__(self, p, f) :
        self.p = p
        self.f = f
    def _parse(self, input, i) :
        i2, res = self.p._parse(input, i)
        return i2, self.f(res)
    def __repr__(self) :
        return "(%r >> %r)" % (self.p, self.f)

class _BindParser(Parser) :
    """Parser(a) -> (a -> Parser(b)) -> Parser(b)"""
    def __init__(self, p, f) :
        self.p = p
        self.f = f
    def _parse(self, input, i) :
        i2, res = self.p._parse(input, i)
        return self.f(res)._parse(input, i2)
    def __repr__(self) :
        return "(%r >= %r)" % (self.p, self.f)

class constp(Parser) :
    """return for bindparser"""
    def __init__(self, v) :
        self.v = v
    def _parse(self, input, i) :
        return i, self.v
    def __repr__(self) :
        return "constp(%r)" % (self.v,)

class _emptyp(Parser) :
    """identity for concatenating parsers"""
    def __init__(self) :
        pass
    def _parse(self, input, i) :
        return i, None
    def __repr__(self) :
        return "emptyp"

emptyp = _emptyp()

class _ConcatParser(Parser) :
    def __init__(self, p1, p2) :
        self.p1 = p1
        self.p2 = p2
    def _parse(self, input, i) :
        i2, res1 = self.p1._parse(input, i)
        i3, res2 = self.p2._parse(input, i2)
        return i3, _Tuple.concat([res1, res2])
    def __repr__(self) :
        return "(%r + %r)" % (self.p1, self.p2)

class _ApParser(Parser) :
    def __init__(self, pf, p) :
        self.pf = pf
        self.p = p
    def _parse(self, input, i) :
        i2, f = self.pf._parse(input, i)
        i3, res = self.p._parse(input, i2)
        return i3, f(res)
    def __repr__(self) :
        return "(%r * %r)" % (self.pf, self.p)

class _EitherParser(Parser) :
    def __init__(self, p1, p2) :
        self.p1 = p1
        self.p2 = p2
    def _parse(self, input, i) :
        try :
            return self.p1._parse(input, i)
        except ParserError as x :
            if x.ateSomething(i) :
                raise
            else :
                try :
                    return self.p2._parse(input, i)
                except ParserError as x2 :
                    if x2.ateSomething(i) :
                        raise
                    else :
                        raise x2.addExpectations(x.expecting)
    def __repr__(self) :
        return "(%r | %r)" % (self.p1, self.p2)

class _ReExpectParser(Parser) :
    def __init__(self, p, msg) :
        self.p = p
        self.msg = msg
    def _parse(self, input, i) :
        try :
            return self.p._parse(input, i)
        except ParserError as x :
            raise x.setExpectations([self.msg])
    def __repr__(self) :
        return "%r.expectsMsg(%r)" % (self.p, self.msg)

class satisfy(Parser) :
    def __init__(self, pred) :
        self.pred = pred
    def _parse(self, input, i) :
        if i >= len(input) :
            raise ParserError.makeError(input, i)
        tok = input[i]
        if self.pred(tok) :
            return i+1, tok
        raise ParserError.makeError(input, i)
    def __repr__(self) :
        return "satisfy(%r)" % (self.pred,)


class _eof(Parser) :
    def __init__(self) :
        pass
    def _parse(self, input, i) :
        if i >= len(input) :
            return i, None
        else :
            raise ParserError.makeError(input, i, ["end of input"])
    def __repr__(self) :
        return "eof"

eof = _eof()

class a(Parser) :
    def __init__(self, ob) :
        self.ob = ob
    def _parse(self, input, i) :
        if i >= len(input) :
            raise ParserError.makeError(input, i, [self.ob])
        tok = input[i]
        if self.ob == tok :
            return i+1, tok
        raise ParserError.makeError(input, i, [self.ob])
    def __repr__(self) :
        return "a(%r)" % self.ob

class many(Parser) :
    def __init__(self, p) :
        self.p = p
    def _parse(self, input, i) :
        ress = []
        while True :
            try :
                i, res = self.p._parse(input, i)
                ress.append(res)
            except ParserError as x :
                if x.ateSomething(i) :
                    raise
                return i, ress
    def __repr__(self) :
        return "many(%r)" % self.p

class FwdDecl(Parser) :
    def __init__(self) :
        self.p = None
    def define(self, p) :
        self.p = p
    def _parse(self, input, i) :
        return self.p._parse(input, i)
    def __repr__(self) :
        return "FwdDecl"

def skip(p) :
    """Matches p but then returns None."""
    return p >> (lambda _ : None)

def many1(p) :
    concat = lambda a : lambda b : [a]+b
    return constp(concat) * p * many(p)

def sepby(p, s) :
    def keep_going(v) :
        concat = lambda v : lambda a : [v]+a
        return constp(concat(v)) * many(skip(s)+p)
    return (p >= keep_going) | constp([])

def sepby1(p, s) :
    concat = lambda a : lambda b : [a]+b
    return constp(concat) * p * many(skip(s)+p)

def between(s1, s2, p) :
    return skip(s1) + p + skip(s2)
