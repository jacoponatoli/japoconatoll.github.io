#!/usr/bin/env python3
"""AMBIENET — i dialoghi dei film.
Cerca nell'Internet Archive film di ogni genere e di ogni lingua (lungometraggi di pubblico dominio: noir, commedie,
fantascienza, film italiani, francesi, tedeschi, giapponesi, russi, messicani, indiani...), ne apre un punto a caso e
ascolta un minuto di audio. Con un rilevatore di voce (WebRTC VAD) trova 7–16 secondi dove si parla davvero, con più
battute separate da pause: un dialogo, non musica né rumore. Salva l'mp3 asciutto in out/f/ e i dati in out/f/index.json;
gli effetti (radio, onde corte, walkie-talkie, telefoni di ogni epoca...) li mette AMBIENET, ogni volta diversi.
Tiene gli ultimi 60 dialoghi."""
import json, os, random, subprocess, sys, urllib.request, urllib.parse, wave, datetime, re

OUT = 'out/f'; os.makedirs(OUT, exist_ok=True)
N = int(os.environ.get('NF', '8')); KEEP = 60
try:
    import webrtcvad
except ImportError:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'webrtcvad-wheels'], check=False)
    import webrtcvad
VAD = webrtcvad.Vad(2)

LINGUE = {   # nome mostrato: come l'Archivio scrive la lingua
    'italiano': 'Italian OR ita', 'francese': 'French OR fre OR fra', 'tedesco': 'German OR ger OR deu', 'spagnolo': 'Spanish OR spa',
    'giapponese': 'Japanese OR jpn', 'russo': 'Russian OR rus', 'portoghese': 'Portuguese OR por', 'cinese': 'Chinese OR chi OR zho OR Mandarin OR Cantonese',
    'hindi': 'Hindi OR hin', 'polacco': 'Polish OR pol', 'ceco': 'Czech OR cze', 'svedese': 'Swedish OR swe', 'greco': 'Greek OR gre',
    'turco': 'Turkish OR tur', 'arabo': 'Arabic OR ara', 'ungherese': 'Hungarian OR hun', 'olandese': 'Dutch OR dut', 'inglese': 'English OR eng'}
COLL = '(collection:feature_films OR collection:film_noir OR collection:SciFi_Horror OR collection:Comedy_Films OR collection:classic_cinema OR collection:foreign_films)'
UA = {'User-Agent': 'AMBIENET (jacoponatoli.net/ambienet)'}

def get(url, t=30):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=t).read()

def cerca(lingua):
    q = f'mediatype:movies AND {COLL} AND language:({LINGUE[lingua]}) AND year:[1929 TO 1972] AND NOT identifier:jesus-film* AND NOT collection:silent_films AND NOT subject:silent'
    base = 'https://archive.org/advancedsearch.php?' + urllib.parse.urlencode({'q': q, 'fl[]': ['identifier', 'title', 'year', 'creator'], 'rows': 100, 'output': 'json'}, doseq=True)
    j = json.loads(get(base + '&page=1')); n = j['response']['numFound']
    if n > 100: j = json.loads(get(base + f'&page={random.randint(1, min(30, (n + 99) // 100))}'))
    return j['response']['docs']

def secondi(x):   # la durata può essere 4405.3, '01:13:25' o '110:58'
    try:
        if isinstance(x, str) and ':' in x:
            v = 0
            for p in x.split(':'): v = v * 60 + float(p)
            return v
        return float(x or 0)
    except ValueError: return 0

def pulisci(t):   # il titolo senza anni, parentesi e note
    t = re.sub(r'\s*[\(\[][^\)\]]*([\)\]]|$)', '', t); t = re.sub(r'^\d{4}\s+', '', t); t = re.sub(r'\s+(19|20)\d\d\s*$', '', t)
    return re.sub(r'\s+', ' ', t).strip(' -_.,') or t

def sorgente(ident):
    m = json.loads(get(f'https://archive.org/metadata/{ident}'))
    fs = [f for f in m.get('files', []) if re.search(r'\.(mp4|ogv|mpeg|mpg|avi|mkv|mp3)$', f.get('name', ''), re.I)]
    if not fs: return None, 0
    pref = lambda f: (0 if f['name'].lower().endswith('.mp3') else 1 if '512kb' in f['name'].lower() else 2 if f['name'].lower().endswith('.mp4') else 3)
    f = sorted(fs, key=pref)[0]; dur = 0
    for g in [f] + fs:
        dur = secondi(g.get('length', 0))
        if dur: break
    return f'https://archive.org/download/{ident}/{urllib.parse.quote(f["name"])}', dur

def ascolta(url, t0, sec=70):
    r = subprocess.run(['timeout', '90', 'ffmpeg', '-y', '-loglevel', 'error', '-ss', str(int(t0)), '-i', url, '-t', str(sec), '-vn', '-ac', '1', '-ar', '32000', 'f.wav'], capture_output=True)
    if r.returncode or not os.path.exists('f.wav'): return None
    with wave.open('f.wav', 'rb') as w: return w.readframes(w.getnframes())

def dialogo(pcm):
    """finestre di 30 ms con voce o senza; cerca 7–16 s densi di voce, con almeno due pause (più battute)"""
    fr = 960 * 2; v = []
    for i in range(0, len(pcm) - fr, fr):
        try: v.append(VAD.is_speech(pcm[i:i + fr], 32000))
        except Exception: v.append(False)
    best = None
    for L in (int(random.uniform(7, 16) / .03),):
        for s in range(0, max(1, len(v) - L), 10):
            w = v[s:s + L]
            if len(w) < L: break
            dens = sum(w) / L
            pause = sum(1 for k in range(1, L) if w[k - 1] and not w[k] and not any(w[k:k + 8]))   # pause di almeno un quarto di secondo
            if dens > .62 and pause >= 2 and w[0]:
                sc = dens + .03 * min(pause, 6)
                if not best or sc > best[0]: best = (sc, s, L)
    if not best: return None
    _, s, L = best
    a = max(0, s - 5); b = min(len(v), s + L + 8)   # un respiro prima e dopo
    while b < len(v) and v[b - 1] and b < s + L + 40: b += 1   # non tagliare una parola a metà
    return a * .03, (b - a) * .03

idx = {'items': []}
if os.path.exists(f'{OUT}/index.json'):
    try: idx = json.load(open(f'{OUT}/index.json', encoding='utf-8'))
    except Exception: pass
idx['items'] = [it for it in idx['items'] if it.get('year', '').isdigit() and 1929 <= int(it['year']) <= 1972]   # solo film sonori fino al 1972
for it in idx['items']: it['title'] = pulisci(it['title'])
fatti = {it['id'] for it in idx['items']}
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'); made = 0; tries = 0
lingue = list(LINGUE)
while made < N and tries < N * 5:
    tries += 1
    lingua = random.choice(lingue + ['inglese', 'inglese'])   # anche l'inglese, ma senza dominare
    try: docs = cerca(lingua)
    except Exception as e: print('ricerca', lingua, e); continue
    docs = [d for d in docs if d['identifier'] not in fatti]
    if not docs: print('niente in', lingua); continue
    d = random.choice(docs)
    try: url, dur = sorgente(d['identifier'])
    except Exception as e: print('metadati', e); continue
    if not url: continue
    t0 = random.uniform(dur * .08, dur * .85) if dur > 600 else random.uniform(60, 900)
    pcm = ascolta(url, t0)
    if not pcm or len(pcm) < 32000 * 2 * 20: print('audio no', d['identifier']); continue
    seg = dialogo(pcm)
    if not seg: print('nessun dialogo', d['identifier']); continue
    a, L = seg; name = f'{d["identifier"][:40]}_{int(t0 + a)}.mp3'.replace('/', '_')
    r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', f'{a:.2f}', '-t', f'{L:.2f}', '-i', 'f.wav',
                        '-af', 'highpass=f=70,afade=t=in:d=0.08,afade=t=out:st=%.2f:d=0.25,loudnorm=I=-20:TP=-2' % max(0, L - .25),
                        '-ac', '1', '-b:a', '48k', f'{OUT}/{name}'], capture_output=True)
    if r.returncode: print('ffmpeg', r.stderr[:200]); continue
    tit = d.get('title') or d['identifier']; tit = pulisci(tit if isinstance(tit, str) else tit[0])
    yr = d.get('year'); yr = (yr[0] if isinstance(yr, list) else yr) or ''
    cr = d.get('creator') or ''; cr = cr[0] if isinstance(cr, list) else cr
    idx['items'].insert(0, {'f': f'f/{name}', 'id': d['identifier'], 'title': tit[:90], 'year': str(yr)[:4], 'creator': cr[:60], 'lang': lingua, 'at': int(t0 + a), 'dur': round(L, 1), 'made': stamp})
    fatti.add(d['identifier']); made += 1
    print(f'{lingua:10s} {L:5.1f}s  {tit[:60]} ({yr})')
idx['items'] = idx['items'][:KEEP]
keep = {os.path.basename(it['f']) for it in idx['items']}
for fn in os.listdir(OUT):
    if fn.endswith('.mp3') and fn not in keep: os.remove(f'{OUT}/{fn}')
idx['updated'] = stamp
json.dump(idx, open(f'{OUT}/index.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
