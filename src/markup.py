# markup.py
# January 2011, Kyle Miller

import tornado.escape
import re

def parse_markup(text) :
    lines = text.splitlines()
    line_num = 0
    tags = dict()
    keys = []

    line_data = []
    reading_tags = True

    tag_ident = re.compile(r"([a-zA-Z0-9][a-zA-Z0-9_]*)")
    while line_num < len(lines) :
        line = lines[line_num].rstrip()
        if reading_tags :
            if not line :
                line_num += 1
                continue
            if line[0] == '@' :
                match = tag_ident.match(line, 1)
                if match :
                    key = match.group(1).lower()
                    if key not in keys :
                        keys.append(key)
                    value = line[match.end(1):].strip()
                    if key in tags :
                        if type(tags[key]) is list :
                            tags[key].append(value)
                        else :
                            tags[key] = [tags[key], value]
                    else :
                        tags[key] = value
                    line_num += 1
                else :
                    reading_tags = False
            else :
                reading_tags = False
        else :
            line_data.append(get_line_prefix(line))
            line_num += 1
    return tags, parse_tags(keys, tags), parse_structure(line_data)

def parse_tags(keys, tags) :
    out = []
    if "title" in keys :
        title = tags["title"]
        if type(title) is list :
            title = title[0]
        out.append("<h1>%s</h1>" % tornado.escape.xhtml_escape(title))
        keys.remove("title")
    if keys :
        out.append("<table class=\"tags\">")
        for key in keys :
            values = tags[key]
            if type(values) is not list :
                values = [values]
            for v in values :
                out.append("<tr><th>%s</th><td>%s</td></tr>" % (tornado.escape.xhtml_escape(key),
                                                                tornado.escape.xhtml_escape(v)))
        out.append("</table>")
    return "\n".join(out)

entity_replace = { "<" : "&lt;",
                   ">" : "&gt;",
                   "&" : "&amp;",
                   }

def parse_paragraph(text) :
    i = 0
    output = []

    # first see if there is a marker at the beginning of the paragraph
    
    if text.startswith("[ ]") :
        output.append("<input type=\"checkbox\" />")
        i += 3
    elif text.startswith("[X]") :
        output.append("<input type=\"checkbox\" checked=\"yes\" />")
        i += 3

    # then continue with the rest

    entity_re = re.compile(r"&(#x?)?[0-9A-Za-z]+;") # cheating :-)
    verbatim_re = re.compile(r"`([^\s].*?[^\s])`")
    italic1_re = re.compile(r"_([^\s].*?[^\s])_")
    italic2_re = re.compile(r"\*([^\s].*?[^\s])\*")
    bold_re = re.compile(r"\*\*([^\s].*?[^\s])\*\*")
    html_re = re.compile(r"</?\w+.*?>")
    plain_re = re.compile(r"[A-Za-z0-9\s]+")
    latex_escape_re = re.compile(r"\$.*?[^\\]\$")
    #url_re = re.compile(r"\b(https?|ftp|file)://[-A-Z0-9+&@#/%?=~_|!:,.;]*[A-Z0-9+&@#/%=~_|]", re.IGNORECASE)

    # http://www.regexguru.com/2008/11/detecting-urls-in-a-block-of-text/
    url_re_safeurl = r"(?:(?:https?|ftp|file)://|www\.|ftp\.)[-A-Z0-9+&@#/%?=~_|$!:,.;]*[-A-Z0-9+&@#/%=~_|$]"
    url_re_email = r"(?:mailto:)?[A-Z0-9._%+-]+@[A-Z0-9._%-]+\.[A-Z]{2,4}\b"
    url_re_dquoteurl = r"\"(?:(?:https?|ftp|file)://|www\.|ftp\.)[^\"\r\n]+\""
    url_re_quoteurl = r"'(?:(?:https?|ftp|file)://|www\.|ftp\.)[^'\r\n]+'"
    url_re = re.compile(r"(\s*)\b(?:(%s)|(%s))|(%s|%s)" % (url_re_safeurl, url_re_email, url_re_dquoteurl, url_re_quoteurl), re.IGNORECASE)

    while i < len(text) :
        if text[i] == "\\" :
            output.append(text[i+1])
            i += 2
            continue
        match = entity_re.match(text, i)
        if match :
            output.append(match.group(0))
            i += len(match.group(0))
            continue
        match = html_re.match(text, i)
        if match :
            output.append(match.group(0))
            i += len(match.group(0))
            continue
        if text[i] in "<>&" :
            output.append(entity_replace[text[i]])
            i += 1
            continue
        # now that we've removed the html, we don't have to worry
        # about touching a url inside an anchor tag
        match = url_re.match(text, i)
        if match :
            email = match.group(3)
            url = tornado.escape.xhtml_escape(match.group(2) or match.group(4) or ("mailto:"+email))
            url_text = tornado.escape.xhtml_escape(match.group(2) or match.group(4) or email)
            output.append("%s<a href=\"%s\">%s</a>" % (match.group(1) or "", url, url_text))
            i += len(match.group(0))
            continue
        match = bold_re.match(text, i)
        if match :
            output.append("<strong>%s</strong>" % parse_paragraph(match.group(1)))
            i += len(match.group(0))
            continue
        match = italic2_re.match(text, i)
        if match :
            output.append("<em>%s</em>" % parse_paragraph(match.group(1)))
            i += len(match.group(0))
            continue
        match = italic1_re.match(text, i)
        if match :
            output.append("<em>%s</em>" % parse_paragraph(match.group(1)))
            i += len(match.group(0))
            continue
        match = verbatim_re.match(text, i)
        if match :
            output.append("<code>%s</code>" % tornado.escape.xhtml_escape(match.group(1)))
            i += len(match.group(0))
            continue
        match = latex_escape_re.match(text, i)
        if match :
            output.append(match.group(0))
            i += len(match.group(0))
            continue
        match = plain_re.match(text, i)
        if match :
            output.append(match.group(0))
            i += len(match.group(0))
            continue
        if text[i] == "-" :
            count = 0
            while text[i] == "-" and i < len(text) :
                count += 1
                i += 1
            if count == 1 :
                output.append("-")
            elif count == 2 :
                output.append("&ndash;")
            else :
                output.append("&mdash;")
            continue

        output.append(text[i])
        i += 1
                
    return "".join(output)

def get_line_prefix(line) :
    """returns (indent, prefix-length, type, prefix, text)"""
    # is it a heading?
    match = re.match(r"^((==+)(\s*))(.*)$", line)
    if match :
        prelen = len(match.group(1))
        return (0, prelen, "heading", match.group(2), match.group(4))
    # is it a list?
    # using -?
    match = re.match(r"^((\s*)(-)(\s*))([^-].*|[^-]?)$", line)
    if match :
        prelen = len(match.group(1))
        return (len(match.group(2)), prelen, "list", match.group(1), match.group(5))
    #using +?
    match = re.match(r"^((\s*)(\+)(\s*))(.*)$", line)
    if match :
        prelen = len(match.group(1))
        return (len(match.group(2)), prelen, "list", match.group(1), match.group(5))
    # is it a quote?
    match = re.match(r"^((\s*)> )(.*)$", line)
    if match :
        prelen = len(match.group(1))
        return (len(match.group(2)), prelen, "quote", match.group(1), get_line_prefix(match.group(3)))
    # so it must be normal.
    match = re.match(r"^(\s*)(.*)$", line)
    prelen = len(match.group(1))
    return (prelen, prelen, None, "", match.group(2))

def parse_par_structure(line_data, line_num, force_paragraph=True) :
    indent = line_data[line_num][1]
    par_type = line_data[line_num][2]
    prefix = line_data[line_num][3]
    start_line = line_num
    blocks = []
    curr_lines = []
    while line_num < len(line_data) :
        ld = line_data[line_num]
        if ld == (0, 0, None, "", "") : # paragraph break
            blocks.append(None)
            if curr_lines :
                blocks.append(("p", parse_paragraph(" ".join(curr_lines))))
                curr_lines = []
            line_num += 1
        elif (ld[0] == indent and ld[2] == None) or (start_line == line_num and ld[2] == "list") : # normal line in paragraph
            if ld[4] != "" :
                curr_lines.append(ld[4])
            line_num += 1
        elif ld[0] > indent and ld[2] == None :
            # code block
            if curr_lines :
                blocks.append(("p-before", parse_paragraph(" ".join(curr_lines))))
                curr_lines = []
            code = []
            code_indent = ld[0]
            while (line_num < len(line_data)
                   and line_data[line_num][2] == None
                   and line_data[line_num][0] >= code_indent) :
                ld = line_data[line_num]
                code.append(" "*(ld[0]-code_indent) + ld[4])
                line_num += 1
            blocks.append((None, "<pre><code>%s</code></pre>" % tornado.escape.xhtml_escape("\n".join(code))))
        elif ld[0] < indent :
            if line_num > 0 and line_data[line_num-1] == (0, 0, None, "", "") :
                line_num -= 1
            break
        elif ld[2] == "list" and ld[0] >= indent :
            if curr_lines :
                blocks.append(("p-before", parse_paragraph(" ".join(curr_lines))))
                curr_lines = []
            line_num, out = parse_list_structure(line_data, line_num)
            blocks.append((None, out))
        elif ld[2] == "quote" and ld[0] >= indent :
            if curr_lines :
                blocks.append(("p-before", parse_paragraph(" ".join(curr_lines))))
                curr_lines = []
            quote_prefix = ld[3]
            quote_line_data = []
            while line_num < len(line_data) and quote_prefix == line_data[line_num][3] :
                quote_line_data.append(line_data[line_num][4])
                line_num += 1
            quote_text = parse_structure(quote_line_data)
            blocks.append((None, "<blockquote>%s</blockquote>" % quote_text))
        else :
            break
    if curr_lines :
        blocks.append(("p", parse_paragraph(" ".join(curr_lines))))
    if len(blocks) == 0 :
        return line_num, ""
    elif len(blocks) == 1 and not force_paragraph :
        return line_num, blocks[0][1]
    else :
        outblocks = []
        last_was_block = False
        for block in blocks :
            if block is None : # line break
                last_was_block = False
            elif block[0] == "p" :
                if last_was_block :
                    outblocks.append("<p class=\"after_block\">%s</p>" % block[1])
                else :
                    outblocks.append("<p>%s</p>" % block[1])
                last_was_block = False
            elif block[0] == "p-before" :
                if last_was_block :
                    outblocks.append("<p class=\"after_block before_block\">%s</p>" % block[1])
                else :
                    outblocks.append("<p class=\"before_block\">%s</p>" % block[1])
                last_was_block = False
            else :
                last_was_block = True
                outblocks.append(block[1])
        return line_num, "\n\n".join(outblocks)

def parse_list_structure(line_data, line_num) :
    prefix = line_data[line_num][3]
    items = []
    while line_num < len(line_data) and line_data[line_num][3] == prefix :
        line_num, out = parse_par_structure(line_data, line_num, force_paragraph=False)
        items.append("<li>%s</li>" % out)
    return line_num, ("<ul>\n%s\n</ul>" % "\n".join(items))

def parse_structure(line_data) :
    line_num = 0
    data = []
    while line_num < len(line_data) :
        ld = line_data[line_num]
        if ld[2] == None :
            line_num, out = parse_par_structure(line_data, line_num)
            data.append(out)
        elif ld[2] == "heading" :
            headingnum = len(ld[3])
            depth = ld[1]
            headingtext = [ld[4]]
            line_num += 1
            while line_num < len(line_data) and line_data[line_num][0] == depth :
                headingtext.append(line_data[line_num][4])
                line_num += 1
            headingtext = parse_paragraph(" ".join(headingtext))
            out = "<h%s>%s</h%s>" % (headingnum, headingtext, headingnum)
            data.append(out)
        elif ld[2] == "list" :
            #print "top level list!?"
            line_num, out = parse_list_structure(line_data, line_num)
            data.append(out)
        else :
            print "?"
            line_num += 1
    return "\n".join(data)

if __name__=="__main__" :
    test = """@title Defining markup syntax
@author Kyle Miller
@category MetaView

I'm trying to figure out a wiki/e-mail-like syntax for the new
MetaView project.  I don't want to spend *too* much time working on
this since IAP only has a couple more weeks left to it.

This is another paragraph & an ampersand.

== What it should support
It should support [links](http://google.com).  Also lists like thus:
- This is the first item.
- This is the second item
  which I've wrapped to
  show one can do such a thing.
- This is the third item.

  And the third item has a second paragraph.
- This is the fourth item.
  - The fourth item has a sublist.
  And can we get back to the fourth item?

It should also support things like **bold** words and `verbatim` words.

Or things can be quoted.
> I am quoting myself, like an e-mail!
> And here is some *markup* inside the blockquote:
> - This is a list with some code:
>     (define (f x)
>       (+ x 2))
> - And just another element.
> Isn't that cool!

There are 2--3 symbols needed (including that one), such as---for instance---these em dashes, and...

The following is code:
  def fact(n) :
    if n <= 1 :
      return n
    else :
      return n*fact(n-1)

== What it should possibly support
It would be nice to have math mode to type things like $x+2$.  This should definitely use some pre-built math library, such as MathJax.

When $a \\ne 0$, there are two solutions to $ax^2 + bx + c = 0$ and they are
$$x = {-b \\pm \\sqrt{b^2-4ac} \\over 2a}$$."""

    print parse_markup(test)[1]
