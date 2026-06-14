#!/usr/bin/env python3
"""Ensure species_explorer.html opens a species card when arriving from compare/graph
(reads sessionStorage 'open_species'). Safe to run more than once."""
import pathlib
p = pathlib.Path('outputs/species_explorer.html')
h = p.read_text(encoding='utf-8')

block = ("\n// open a species card when arriving from compare / graph\n"
         "(function(){try{var want=sessionStorage.getItem('open_species');"
         "if(want){sessionStorage.removeItem('open_species');"
         "setTimeout(function(){if(typeof openSp==='function')openSp(want);},150);}}catch(e){}})();\n")

if 'open_species' in h:
    print('Already wired: species_explorer reads open_species. No change needed.')
elif 'loadIndex();' in h:
    h = h.replace('loadIndex();', 'loadIndex();' + block, 1)
    p.write_text(h, encoding='utf-8'); print('Handler injected after loadIndex().')
else:
    i = h.rfind('</script>')
    h = h[:i] + block + h[i:]
    p.write_text(h, encoding='utf-8'); print('Handler injected before </script>.')