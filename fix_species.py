#!/usr/bin/env python3
"""Repair outputs/species_explorer.html when the page is stuck on 'species loading'.
Re-serialises the embedded data as safe, pure-ASCII JS (escapes invisible line
separators and neutralises </script), keeping all species and recordings."""
import re, json
from pathlib import Path

p = Path('outputs/species_explorer.html')
h = p.read_text(encoding='utf-8')

def extract(h):
    i = h.find('const EMBEDDED_DB')
    if i < 0:
        raise SystemExit('EMBEDDED_DB not found')
    eq = h.find('[', i)
    depth = 0; instr = False; esc = False; end = None
    for j in range(eq, len(h)):
        c = h[j]
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
    return eq, end

def js_to_json(s):
    out = []; i = 0; n = len(s)
    while i < n:
        c = s[i]
        if c == '\\' and i + 1 < n:
            nx = s[i + 1]
            if nx in '"\\/bfnrt': out.append(c); out.append(nx); i += 2; continue
            if nx == 'u' and re.match(r'[0-9a-fA-F]{4}', s[i + 2:i + 6]): out.append('\\u'); i += 2; continue
            out.append('\\\\'); i += 1; continue
        out.append(c); i += 1
    return ''.join(out)

eq, end = extract(h)
data = json.loads(js_to_json(h[eq:end + 1]), strict=False)

# pure ASCII escapes EVERYTHING risky (U+2028/U+2029, control chars, non-ascii);
# the </ -> <\/ swap stops any string from closing the <script> tag early.
js = json.dumps(data, ensure_ascii=True, separators=(',', ':')).replace('</', '<\\/')
Path('outputs/species_explorer.html').write_text(h[:eq] + js + h[end + 1:], encoding='utf-8')
print('OK. specie:', len(data),
      '| con audio:', sum(1 for s in data if s.get('recordings')))