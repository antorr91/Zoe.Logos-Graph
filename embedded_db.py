#!/usr/bin/env python3
"""
embedded_db.py - Zoe.Logos-Graph

Robust read/write for the `const EMBEDDED_DB = [ ... ];` array embedded in the
HTML pages. The array is a JavaScript literal, so it can contain control chars
and escapes that strict json.loads rejects; this module sanitises them on read
and writes back pure-ASCII, </script-safe JSON.

    import embedded_db as edb
    species, eq, end = edb.load(html)      # parse
    html = edb.write(html, species, eq, end)   # splice back
"""
import re, json


def _js_to_json(s):
    out = []; i = 0; n = len(s)
    while i < n:
        c = s[i]
        if c == '\\' and i + 1 < n:
            nx = s[i + 1]
            if nx in '"\\/bfnrt':
                out.append(c); out.append(nx); i += 2; continue
            if nx == 'u' and re.match(r'[0-9a-fA-F]{4}', s[i + 2:i + 6]):
                out.append('\\u'); i += 2; continue
            out.append('\\\\'); i += 1; continue
        out.append(c); i += 1
    return ''.join(out)


def extract(html, marker='const EMBEDDED_DB'):
    i = html.find(marker)
    if i < 0:
        raise ValueError('%s not found' % marker)
    eq = html.find('[', i)
    depth = 0; instr = False; esc = False; end = None
    for j in range(eq, len(html)):
        c = html[j]
        if instr:
            if esc: esc = False
            elif c == '\\': esc = True
            elif c == '"': instr = False
        else:
            if c == '"': instr = True
            elif c == '[': depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    end = j; break
    if end is None:
        raise ValueError('could not bracket-match the array')
    return eq, end


def load(html, marker='const EMBEDDED_DB'):
    eq, end = extract(html, marker)
    species = json.loads(_js_to_json(html[eq:end + 1]), strict=False)
    return species, eq, end


def write(html, species, eq, end):
    js = json.dumps(species, ensure_ascii=True, separators=(',', ':')).replace('</', '<\\/')
    return html[:eq] + js + html[end + 1:]
