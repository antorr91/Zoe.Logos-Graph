#!/usr/bin/env python3
"""
fetch_recordings.py - Zoe.Logos-Graph

Check and top up the recordings shown in the Media tab of the species page.

  1. CHECK what is already there: links that are not audio files (Vimeo, archive.org
     pages, Xeno-Canto pages) are removed, http links become https (browsers block
     http audio on an https site), iNaturalist recordings whose observation is now
     identified as another species, or is 'casual' (no date, place or community
     check), are removed, Xeno-Canto recordings of quality D and E are removed,
     broken links are removed. The best recordings are listed first.
  2. TOP UP species with fewer than --per-species recordings from
       Xeno-Canto (birds, frogs, insects, bats; needs XC_API_KEY)
       iNaturalist (research-grade observations with sound, any animal)
       GBIF (sound records with a Creative Commons licence)
     Every new recording must be identified as the same species (or a synonym).

  python fetch_recordings.py                   check + top up
  python fetch_recordings.py --offline         only the checks that need no internet
  python fetch_recordings.py --species "Parus major"
"""
import os, re, time, argparse
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import atlas

ap = argparse.ArgumentParser()
ap.add_argument('--per-species', type=int, default=8)
ap.add_argument('--offline', action='store_true')
ap.add_argument('--species', default='')
args = ap.parse_args()

XC_KEY = os.environ.get('XC_API_KEY', '')
XC_CLASSES = {'Aves', 'Amphibia', 'Insecta'}
AUDIO_EXT = {'mp3': 'audio/mpeg', 'mpga': 'audio/mpeg', 'm4a': 'audio/mp4', 'mp4': 'audio/mp4',
             'wav': 'audio/wav', 'ogg': 'audio/ogg', 'oga': 'audio/ogg', 'flac': 'audio/flac'}


def mime(url):
    return AUDIO_EXT.get(urlparse(url or '').path.rsplit('.', 1)[-1].lower(), '')


def playable(url):
    """a direct audio file (or the Xeno-Canto download link), not a web page"""
    return bool(mime(url)) or bool(re.match(r'https://xeno-canto\.org/\d+/download$', url or ''))


def tidy(r):
    r = dict(r)
    for f in ('audio', 'sono', 'url'):
        v = r.get(f) or ''
        if v.startswith('//'):
            v = 'https:' + v
        if v.startswith('http://'):
            v = 'https://' + v[7:]
        if f == 'audio':
            v = v.replace('://archive.org/details/', '://archive.org/download/')   # the file, not the page
        r[f] = v
    if r.get('source') in ('inat', 'gbif') and r.get('type') in ('', 'call', None):
        r['type'] = 'recording'          # iNaturalist and GBIF do not say which call it is
    r['mime'] = mime(r['audio'])
    return r


def reachable(url):
    try:
        req = Request(url, headers={'User-Agent': atlas.UA, 'Range': 'bytes=0-1'})
        with urlopen(req, timeout=20) as r:
            return r.status < 400
    except HTTPError as e:                      # the server answered: only 'not found' means the file is gone
        return e.code not in (404, 410)
    except Exception:
        return False


def accepted_names(sci, syn):
    out = {sci.lower()}
    for part in ('manual', 'gbif'):
        out |= {n.lower() for n in (syn.get(part) or {}).get(sci, [])}
    return out


def same_species(name, accepted):
    name = (name or '').lower().strip()
    return any(name == a or name.startswith(a + ' ') for a in accepted)    # subspecies count


def inat_check(species, syn):
    """remove iNaturalist recordings whose observation is identified as something else or is
    casual; keep the quality grade (research, needs_id) to show it on the page"""
    obs = {}
    for s in species:
        for r in s.get('recordings') or []:
            m = re.search(r'/observations/(\d+)', r.get('url') or '')
            if r.get('source') == 'inat' and m:
                obs[m.group(1)] = None
    ids = sorted(obs)
    print('iNaturalist: checking %d observations (about %d minutes)' % (len(ids), len(ids) // 100 // 30 + 1), flush=True)
    failed = 0
    for i in range(0, len(ids), 100):
        if i and i % 500 == 0:
            print('  %d/%d' % (i, len(ids)), flush=True)
        data = atlas.get_json('https://api.inaturalist.org/v1/observations?' + urlencode(
            {'id': ','.join(ids[i:i + 100]), 'per_page': 100}), tries=2, timeout=20)
        failed = failed + 1 if data is None else 0
        if failed == 3:                                 # not answering today: check them next time
            print('  iNaturalist is not answering, the check is skipped this time')
            break
        for o in (data or {}).get('results') or []:
            obs[str(o['id'])] = ((o.get('taxon') or {}).get('name') or '', o.get('quality_grade'))
        time.sleep(1)                                   # iNaturalist asks for ~1 request per second
    dropped = 0
    for s in species:
        acc = accepted_names(s['sci'], syn)
        keep = []
        for r in s.get('recordings') or []:
            m = re.search(r'/observations/(\d+)', r.get('url') or '')
            got = obs.get(m.group(1)) if (r.get('source') == 'inat' and m) else None
            if got and (not same_species(got[0], acc) or got[1] == 'casual'):
                dropped += 1
                continue
            if got:
                r['q'] = got[1] or ''
            keep.append(r)
        s['recordings'] = keep
    print('iNaturalist: %d observations checked, %d recordings removed (other species or casual)' % (len(ids), dropped))


def xc_usable(r):
    """quality A or B, a sound type the recordist is sure of, not an unattended recorder"""
    return (r.get('q') in ('A', 'B') and 'uncertain' not in (r.get('type') or '').lower()
            and (r.get('auto') or '').lower() != 'yes')


def xc_sono(r):
    sono = r.get('sono') or {}
    url = sono.get('large') or sono.get('med') or ''
    return ('https:' + url) if url.startswith('//') else url


def xc_also(r):
    """other species audible in the background, as the recordist listed them"""
    return ', '.join(a for a in (r.get('also') or []) if a)[:120]


def xc_refresh(species):
    """Xeno-Canto recordings saved before quality and background species were kept:
    ask Xeno-Canto again (ratings change over time) and keep only the usable ones"""
    if not XC_KEY:
        return
    todo = [(s, r) for s in species for r in s['recordings'] if r.get('source') == 'xc' and 'also' not in r]
    if not todo:
        return
    print('Xeno-Canto: checking %d recordings saved before quality was recorded (about %d minutes)'
          % (len(todo), len(todo) // 120 + 1))
    dropped = set()
    for n, (s, r) in enumerate(todo, 1):
        data = atlas.get_json('https://xeno-canto.org/api/3/recordings?' + urlencode(
            {'query': 'nr:%s' % r['id'], 'key': XC_KEY}))
        found = (data or {}).get('recordings') or []
        if data is None:                                 # no answer: keep it, try next time
            continue
        if not found or not xc_usable(found[0]):
            dropped.add(id(r))
            continue
        x = found[0]
        r.update(q=x.get('q') or r.get('q', ''), sono=xc_sono(x) or r.get('sono', ''), also=xc_also(x),
                 type=(x.get('type') or r.get('type') or 'recording').lower())
        if n % 100 == 0:
            print('  %d/%d' % (n, len(todo)))
        time.sleep(0.3)
    for s in species:
        s['recordings'] = [r for r in s['recordings'] if id(r) not in dropped]
    print('Xeno-Canto: %d recordings removed (quality C-E, uncertain type, automatic recorder, or deleted)'
          % len(dropped))


def from_xc(sci, acc):
    if not XC_KEY or len(sci.split()) < 2:
        return []
    g, sp = sci.split()[:2]
    data = atlas.get_json('https://xeno-canto.org/api/3/recordings?' + urlencode(
        {'query': 'gen:%s sp:%s q:">C"' % (g, sp), 'key': XC_KEY, 'per_page': 100}))
    out = []
    for r in (data or {}).get('recordings') or []:
        if not same_species('%s %s' % (r.get('gen', ''), r.get('sp', '')), acc) or not r.get('file'):
            continue
        if not xc_usable(r):
            continue
        lic = re.search(r'licenses/([a-z-]+)/([\d.]+)', r.get('lic') or '')
        out.append(tidy({'source': 'xc', 'id': str(r.get('id')), 'type': (r.get('type') or 'recording').lower(),
                         'q': r.get('q') or '', 'rec': r.get('rec') or '', 'date': r.get('date') or '',
                         'cnt': r.get('cnt') or '', 'loc': r.get('loc') or '', 'duration': r.get('length') or '',
                         'audio': r['file'], 'sono': xc_sono(r), 'also': xc_also(r),
                         'url': 'https://xeno-canto.org/%s' % r.get('id'),
                         'license': 'CC %s %s' % (lic.group(1).upper(), lic.group(2)) if lic else ''}))
    return out


def from_inat(sci, acc):
    data = atlas.get_json('https://api.inaturalist.org/v1/observations?' + urlencode(
        {'taxon_name': sci, 'sounds': 'true', 'quality_grade': 'research', 'per_page': 30, 'order_by': 'votes'}))
    time.sleep(1)
    out = []
    for o in (data or {}).get('results') or []:
        if not same_species((o.get('taxon') or {}).get('name'), acc):
            continue
        for snd in o.get('sounds') or []:
            if snd.get('file_url') and snd.get('license_code'):
                out.append(tidy({'source': 'inat', 'id': str(snd.get('id')), 'type': 'recording', 'q': 'research',
                                 'rec': (o.get('user') or {}).get('login') or '', 'date': o.get('observed_on') or '',
                                 'cnt': o.get('place_guess') or '', 'duration': '', 'audio': snd['file_url'],
                                 'sono': '', 'url': 'https://www.inaturalist.org/observations/%s' % o['id'],
                                 'license': snd['license_code'].upper()}))
                break
    return out


def from_gbif(sci, acc):
    data = atlas.get_json('https://api.gbif.org/v1/occurrence/search?' + urlencode(
        {'scientificName': sci, 'mediaType': 'Sound', 'limit': 30}))
    out = []
    for occ in (data or {}).get('results') or []:
        if not same_species(occ.get('species') or occ.get('scientificName'), acc):
            continue
        for m in occ.get('media') or []:
            lic = m.get('license') or occ.get('license') or ''
            if m.get('type') == 'Sound' and playable(m.get('identifier')) and re.search(r'creativecommons|cc', lic, re.I):
                ver = re.search(r'licenses/([a-z-]+)/([\d.]+)', lic)
                out.append(tidy({'source': 'gbif', 'id': str(occ.get('key')), 'type': 'recording', 'q': '',
                                 'rec': m.get('rightsHolder') or m.get('creator') or '',
                                 'date': (occ.get('eventDate') or '')[:10], 'cnt': occ.get('country') or '',
                                 'duration': '', 'audio': m['identifier'], 'sono': '',
                                 'url': 'https://www.gbif.org/occurrence/%s' % occ.get('key'),
                                 'license': 'CC %s %s' % (ver.group(1).upper(), ver.group(2)) if ver else lic}))
                break
    return out


# best first: Xeno-Canto A and iNaturalist research grade, then B, needs ID, unknown, C
RANK = {'A': 0, 'research': 0, 'B': 1, 'needs_id': 2, '': 3}


def best_first(recs):
    return sorted(recs, key=lambda r: (RANK.get(r.get('q') or '', 3), bool(r.get('also'))))


def main():
    html, species, eq, end = atlas.load_species()
    syn = atlas.read_json(atlas.SYNONYMS, {})
    before = sum(len(s.get('recordings') or []) for s in species)

    # 1. checks
    bad = 0
    for s in species:
        recs = [tidy(r) for r in s.get('recordings') or []]
        good = [r for r in recs if playable(r['audio']) and r.get('q') not in ('C', 'D', 'E')
                and 'uncertain' not in (r.get('type') or '')]
        bad += len(recs) - len(good)
        seen = set()
        s['recordings'] = [r for r in good if not (r['audio'] in seen or seen.add(r['audio']))]
    print('not audio files (web pages, videos), quality C-E, uncertain type, or duplicates removed: %d' % bad)
    if args.offline:
        for s in species:
            s['recordings'] = best_first(s['recordings'])
        atlas.save_species(html, species, eq, end)
        return
    inat_check(species, syn)
    xc_refresh(species)
    samples = {}                                       # a few files per archive are enough to spot a dead one
    for s in species:
        for r in s['recordings']:
            h = urlparse(r['audio']).netloc
            if 'inaturalist' not in h and 'xeno-canto' not in h and len(samples.setdefault(h, [])) < 3:
                samples[h].append(r['audio'])
    print('checking that the other archives still answer (%d)' % len(samples))
    dead = {h for h, urls in samples.items() if not any(reachable(u) for u in urls)}
    if dead and len(dead) == len(samples):             # all of them at once: the problem is our connection
        print('no archive answers, probably a connection problem: nothing removed')
        dead = set()
    for s in species:
        s['recordings'] = [r for r in s['recordings'] if urlparse(r['audio']).netloc not in dead]
    if dead:
        print('removed recordings from unreachable archives: ' + ', '.join(sorted(dead)))

    # 2. top up
    added = 0
    for n, s in enumerate(species, 1):
        if args.species and s['sci'] != args.species:
            continue
        recs = s['recordings']
        if len(recs) >= args.per_species:
            continue
        acc = accepted_names(s['sci'], syn)
        fresh = []
        if s.get('class_') in XC_CLASSES or (s.get('order_') or '').lower() == 'chiroptera':
            fresh += from_xc(s['sci'], acc)
        if len(recs) + len(fresh) < args.per_species:
            fresh += from_inat(s['sci'], acc)
        if len(recs) + len(fresh) < args.per_species:
            fresh += from_gbif(s['sci'], acc)
        have = {r['audio'] for r in recs}
        fresh = [r for r in fresh if r['audio'] not in have]
        # Xeno-Canto first (call types and quality grades), one recording per call type first
        fresh.sort(key=lambda r: (r['source'] != 'xc', r.get('q') not in ('A', 'B')))
        types = {r['type'] for r in recs}
        for r in [r for r in fresh if r['type'] not in types] + [r for r in fresh if r['type'] in types]:
            if len(recs) >= args.per_species:
                break
            if r['audio'] not in have:
                recs.append(r); have.add(r['audio']); types.add(r['type']); added += 1
        if n % 100 == 0:
            print('  %d/%d species, %d recordings added' % (n, len(species), added))

    for s in species:
        s['recordings'] = best_first(s['recordings'])
    atlas.save_species(html, species, eq, end)
    after = sum(len(s['recordings']) for s in species)
    print('recordings: %d -> %d (%d added). Species with recordings: %d/%d'
          % (before, after, added, sum(1 for s in species if s['recordings']), len(species)))


if __name__ == '__main__':
    main()
