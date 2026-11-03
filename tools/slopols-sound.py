#!/usr/bin/env python3
"""SLOPOLS — suoni del mare.

Ogni giro cerca registrazioni di mare, onde, acqua, sott'acqua su archivi aperti
(Wikimedia Commons, Internet Archive; Freesound se c'è la chiave FREESOUND_KEY),
ne taglia un pezzo a caso, lo normalizza e lo aggiunge all'archivio.
L'archivio tiene gli ultimi KEEP pezzi: i più vecchi escono, così il suono si rinnova sempre.
Solo licenze libere (Creative Commons, pubblico dominio); i crediti finiscono in list.json.

uso: python3 tools/slopols-sound.py <cartella-archivio>
"""
import json, os, random, re, subprocess, sys, time, hashlib, urllib.parse, urllib.request

OUT = sys.argv[1] if len(sys.argv) > 1 else 'data'
KEEP = 60            # pezzi nell'archivio
NEW = 8              # nuovi pezzi per giro (24 al primo giro)
UA = 'SLOPOLS/1.0 (art project; https://jacoponatoli.net/slopols/)'
QUERIES = ['sea waves', 'ocean waves', 'surf', 'waves beach', 'underwater', 'hydrophone', 'sea shore',
           'ocean ambience', 'waves rocks', 'harbour water', 'bubbles water', 'water drops', 'tide',
           'mare onde', 'mer vagues', 'Meeresrauschen', 'stream water', 'boat water splash']
# solo registrazioni d'acqua: il titolo deve parlare di mare/acqua, e niente musica, voci, toni di prova
GOOD = re.compile(r'\b(sea|seas|ocean|oceans|waves|surf|underwater|hydrophone|beach|shore|seashore|coast|tide|tides|harbou?r|'
                  r'splash\w*|bubbl\w*|water|stream|river|creek|brook|lake|rain|mare|onde|acqua|spiaggia|mer|vagues|eau|'
                  r'meer|wasser|wellen|olas|agua|marina|marine|porto|scogli\w*|rocks)\b', re.I)
BAD = re.compile(r'(podcast|episode|edition|weekly|interview|news|music|song|melody|loop|sine|sitar|chill|album|track|'
                 r'remix|\bmix\b|#\s?\d|lecture|sermon|talk|audiobook|chapter|cast\b|radio show|meditation|relax|'
                 r'piano|guitar|ambient music|isrc|feat\.|ft\.|conversation|session|party|\bdub\b|\(with|baptism|church|show|'
                 r'concert|band|lyrics|vocal|singing|choir|story|reading|poem)', re.I)
def relevant(title): return bool(GOOD.search(title or '')) and not BAD.search(title or '')
OK_LIC = re.compile(r'(cc[- ]?0|cc[- ]?by|creativecommons|public ?domain|publicdomain|pd)', re.I)

def get(url, as_json=True, timeout=40):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return json.loads(data) if as_json else data

def commons(q):
    url = 'https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode({
        'action': 'query', 'format': 'json', 'generator': 'search', 'gsrnamespace': 6,
        'gsrsearch': f'{q} filetype:audio', 'gsrlimit': 50, 'gsroffset': random.choice([0, 0, 50, 100]),
        'prop': 'imageinfo', 'iiprop': 'url|size|mime|extmetadata'})
    out = []
    for p in (get(url).get('query', {}).get('pages', {}) or {}).values():
        ii = (p.get('imageinfo') or [{}])[0]
        meta = ii.get('extmetadata', {})
        lic = meta.get('LicenseShortName', {}).get('value', '')
        if not ii.get('url') or ii.get('size', 0) > 60e6 or not OK_LIC.search(lic):
            continue
        author = re.sub('<[^>]+>', '', meta.get('Artist', {}).get('value', '')).strip()[:80]
        out.append({'id': 'wc:' + str(p['pageid']), 'src': 'Wikimedia Commons', 'url': ii['url'],
                    'page': ii.get('descriptionurl', ''), 'title': p['title'].replace('File:', ''),
                    'author': author, 'license': lic})
    return out

def archive(q):
    url = 'https://archive.org/advancedsearch.php?' + urllib.parse.urlencode({
        'q': f'title:({q}) AND mediatype:audio AND licenseurl:*', 'fl[]': ['identifier', 'title', 'licenseurl', 'creator'],
        'rows': 60, 'page': random.randint(1, 3), 'output': 'json'}, doseq=True)
    out = []
    for d in get(url).get('response', {}).get('docs', []):
        lic = d.get('licenseurl', '')
        if not OK_LIC.search(lic):
            continue
        out.append({'id': 'ia:' + d['identifier'], 'src': 'Internet Archive', 'ia': d['identifier'],
                    'page': 'https://archive.org/details/' + d['identifier'], 'title': str(d.get('title', ''))[:120],
                    'author': str(d.get('creator', ''))[:80], 'license': lic})
    return out

def archive_file(c):
    m = get('https://archive.org/metadata/' + c['ia'])
    files = [f for f in m.get('files', []) if re.search(r'mp3|ogg|flac|wav', f.get('format', ''), re.I)
             and 2e5 < int(f.get('size', 0) or 0) < 60e6]
    if not files:
        return None
    f = random.choice(files)
    return 'https://archive.org/download/' + c['ia'] + '/' + urllib.parse.quote(f['name'])

def freesound(q, key):
    url = 'https://freesound.org/apiv2/search/text/?' + urllib.parse.urlencode({
        'query': q, 'fields': 'id,name,username,license,previews,url', 'filter': 'duration:[12 TO 900]',
        'page_size': 40, 'page': random.randint(1, 3), 'token': key})
    out = []
    for s in get(url).get('results', []):
        out.append({'id': 'fs:' + str(s['id']), 'src': 'Freesound', 'url': s['previews']['preview-hq-mp3'],
                    'page': s['url'], 'title': s['name'], 'author': s['username'], 'license': s['license']})
    return out

def duration(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                       capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except ValueError: return 0

def cut(src, dst):
    d = duration(src)
    if d < 8:
        return 0
    seg = min(d, random.uniform(35, 75))
    start = random.uniform(0, max(0, d - seg))
    af = f'loudnorm=I=-20:TP=-2,afade=t=in:d=1.5,afade=t=out:st={max(0, seg - 2):.2f}:d=2'
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{start:.2f}', '-t', f'{seg:.2f}', '-i', src,
                        '-af', af, '-ac', '2', '-ar', '44100', '-b:a', '128k', dst], capture_output=True)
    return seg if r.returncode == 0 and os.path.getsize(dst) > 20000 else 0

def main():
    os.makedirs(OUT, exist_ok=True)
    lp, sp = os.path.join(OUT, 'list.json'), os.path.join(OUT, 'seen.json')
    items = json.load(open(lp)) if os.path.exists(lp) else []
    seen = set(json.load(open(sp))) if os.path.exists(sp) else set()
    for old in [c for c in items if not relevant(c['title'])]:   # via quello che non è acqua
        try: os.remove(os.path.join(OUT, old['file']))
        except OSError: pass
    items = [c for c in items if relevant(c['title'])]
    want = NEW if len(items) >= 30 else 24
    key = os.environ.get('FREESOUND_KEY', '')

    cands = []
    for q in random.sample(QUERIES, 12):
        for fn in (commons, archive) + ((lambda q: freesound(q, key)),) * bool(key):
            try: cands += fn(q)
            except Exception as e: print('search', q, e)
            time.sleep(0.5)
    cands = [c for c in {c['id']: c for c in cands}.values() if c['id'] not in seen and relevant(c['title'])]
    random.shuffle(cands)
    print('candidati nuovi:', len(cands))

    added = 0
    for c in cands:
        if added >= want:
            break
        seen.add(c['id'])
        try:
            url = c.get('url') or archive_file(c)
            if not url:
                continue
            raw = get(url, as_json=False, timeout=120)
            tmp = '/tmp/in.' + (url.rsplit('.', 1)[-1][:4] or 'bin')
            open(tmp, 'wb').write(raw)
            name = f"{int(time.time()*1000)}-{hashlib.md5(c['id'].encode()).hexdigest()[:8]}.mp3"
            seg = cut(tmp, os.path.join(OUT, name))
            if not seg:
                continue
            c.update(file=name, dur=round(seg, 1))
            c.pop('url', None); c.pop('ia', None)
            items.append(c); added += 1
            print('+', c['src'], '|', c['title'][:60], '|', c['license'])
        except Exception as e:
            print('skip', c['id'], e)

    items.sort(key=lambda c: c['file'])
    for old in items[:-KEEP]:
        try: os.remove(os.path.join(OUT, old['file']))
        except OSError: pass
    items = items[-KEEP:]
    json.dump(items, open(lp, 'w'), ensure_ascii=False, indent=0)
    json.dump(sorted(seen), open(sp, 'w'))
    print(f'aggiunti {added}, in archivio {len(items)}')

if __name__ == '__main__':
    main()
