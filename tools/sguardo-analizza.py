# SGUARDO — l'atlante che cresce. Gira su GitHub Actions, mai nel browser dei visitatori.
#
# 1. Le opere scelte a mano (sguardo/opere.json) vengono sempre analizzate.
# 2. Ogni giro pesca nuovi dipinti di nudo da Wikidata/Wikimedia Commons e li aggiunge
#    all'atlante SOLO se: (a) nessun soggetto dichiarato e nessuna parola del titolo
#    rimanda a bambini, putti, Cupido, Gesù Bambino...; (b) CLIP non vede bambini nell'immagine
#    (intera, a riquadri e attorno a ogni genitale trovato); (c) NudeNet ci trova dei genitali.
#    Nel dubbio si scarta. Gli scartati vanno in sguardo/scartati.json e non vengono riprovati.
# 3. sguardo/esclusi.json: nomi di file da togliere a mano, per sempre.
# Risultato: sguardo/punti.json (genitali + mappa della pelle per ogni dipinto).
import json, os, re, time, tempfile, io, random
import requests
from PIL import Image
from nudenet import NudeDetector

VERSION = 5
BUDGET = int(os.environ.get('SGUARDO_BUDGET', '45'))    # dipinti analizzati per giro
MAX_ATLAS = 800
UA = {'User-Agent': 'SGUARDO/1.0 (https://jacoponatoli.net/sguardo/) python-requests'}
CROP = 0.03
KEEP = {'FEMALE_GENITALIA_EXPOSED': 'vulva', 'MALE_GENITALIA_EXPOSED': 'pene',
        'FEMALE_GENITALIA_COVERED': 'vulva coperta', 'ANUS_EXPOSED': 'ano'}
CHILD_WORDS = re.compile(r"child|infant|baby|babies|boy|girl|putto|putti|cupid|amor\b|amore|amorini|eros|cherub|"
                         r"christ child|bambin|fanciull|ragazz|enfant|kind|knabe|mädchen|niño|niña|toddler|"
                         r"madonna|virgin and|holy family|sacra famiglia|nativity|natività|adoration|adorazione|"
                         r"innocents|innocenti|youth|adolescent|teen|son\b|daughter|figli|venus and cupid|"
                         r"amour|angel|angeli|angioletti|lolita|young girl|jeune fille|"
                         # età nel titolo, in più lingue
                         r"\b([1-9]|1[0-7])\s*(år|ar|anni|ans|years|jahre|jaar|años)\b|years old|"
                         r"twelve|thirteen|fourteen|fifteen|sixteen|seventeen|dodic|tredic|quattordic|quindic|sedic|diciassett|"
                         r"tolv|tretton|fjorton|femton|sexton|sjutton|douze|treize|quatorze|quinze|seize|dix-sept|"
                         r"zwölf|dreizehn|vierzehn|fünfzehn|sechzehn|siebzehn|pubert|virgin\b|vergine|maiden|"
                         # pittori che hanno ritratto modelle o modelli minorenni: mai pescati
                         r"zorn|bouguereau|schiele|kirchner|gauguin|heckel|pechstein|balthus|mueller|müller|"
                         r"carroll|flandrin|tuke|scott tuke|von gloeden|eakins|larsson|mucha", re.I)

def load(path, default):
    try: return json.load(open(path))
    except Exception: return default

atlas = {e['f']: e for e in load('sguardo/punti.json', [])}
esclusi = set(load('sguardo/esclusi.json', []))
scartati = set(load('sguardo/scartati.json', []))
voce_old = load('sguardo/voce.json', {})
motivi = voce_old.get('motivi', {})
works = load('sguardo/opere.json', [])
curated = {}
for w in works:
    for f in w['f']: curated[f] = w

# ---------- Commons ----------
def imageinfo(files):
    info = {}
    for i in range(0, len(files), 40):
        try:
            r = requests.get('https://commons.wikimedia.org/w/api.php', headers=UA, timeout=60, params={
                'action': 'query', 'format': 'json', 'prop': 'imageinfo', 'iiprop': 'size|url|mime',
                'iiurlwidth': 1920, 'titles': '|'.join('File:' + f for f in files[i:i + 40])}).json()
        except Exception as e:
            print('commons:', e); continue
        q = r.get('query', {})
        norm = {n['to']: n['from'] for n in q.get('normalized', [])}
        for p in q.get('pages', {}).values():
            ii = (p.get('imageinfo') or [None])[0]
            if not ii or not ii.get('width') or min(ii['width'], ii['height']) < 650:
                continue
            v = dict(width=ii['width'], height=ii['height'], url=ii['url'], thumb=ii.get('thumburl', ''),
                     mime=ii.get('mime', ''), size=ii.get('size', 0))
            info[norm.get(p['title'], p['title'])[5:].replace('_', ' ')] = v
            info[p['title'][5:]] = v
        time.sleep(1)
    return info

# ---------- Wikidata: dipinti che raffigurano nudi ----------
def qid(label):
    try:
        r = requests.get('https://www.wikidata.org/w/api.php', headers=UA, timeout=30, params={
            'action': 'wbsearchentities', 'search': label, 'language': 'en', 'format': 'json', 'limit': 1}).json()
        return r['search'][0]['id'] if r.get('search') else None
    except Exception:
        return None

def discover():
    ids = {q for q in (qid(l) for l in ['nudity', 'female nude', 'male nude', 'nude (art)', 'female nudity', 'male nudity']) if q}
    kids = {q for q in (qid(l) for l in ['child', 'infant', 'boy', 'girl', 'putto', 'Cupid', 'Christ Child', 'cherub',
                                        'angel', 'Madonna and Child', 'baby', 'toddler', 'adolescent', 'Eros', 'Amor']) if q}
    print('soggetti:', ids, 'esclusi:', kids)
    if not ids: return []
    q = ('SELECT DISTINCT ?item ?img ?label ?date WHERE { VALUES ?n { ' + ' '.join('wd:' + i for i in ids) + ' } '
         '?item wdt:P180 ?n ; wdt:P31 wd:Q3305213 ; wdt:P18 ?img . '
         'FILTER NOT EXISTS { VALUES ?c { ' + ' '.join('wd:' + i for i in kids) + ' } ?item wdt:P180 ?c } '
         'OPTIONAL { ?item rdfs:label ?label FILTER(LANG(?label)="en") } OPTIONAL { ?item wdt:P571 ?date } } LIMIT 8000')
    r = None
    for t in range(3):
        try:
            resp = requests.get('https://query.wikidata.org/sparql', headers=dict(UA, Accept='application/sparql-results+json'),
                                params={'query': q}, timeout=150)
            r = resp.json(); break
        except Exception as e:
            print('wikidata:', e, resp.status_code if 'resp' in dir() else ''); time.sleep(20)
    if not r: return []
    out = []
    for b in r['results']['bindings']:
        f = requests.utils.unquote(b['img']['value'].split('Special:FilePath/')[-1]).replace('_', ' ')
        text = ' '.join([f, b.get('label', {}).get('value', '')])
        if CHILD_WORDS.search(text):
            continue
        qq = b['item']['value'].rsplit('/', 1)[-1]
        yr = None
        try: yr = int(b['date']['value'][:5].lstrip('+')) if 'date' in b else None
        except Exception: pass
        out.append((f, yr, qq))
    seen, uniq = set(), []
    for t in out:
        if t[2] in seen: continue
        seen.add(t[2]); uniq.append(t)
    out = uniq
    print('candidati da Wikidata:', len(out))
    return out

# ---------- modelli ----------
det = NudeDetector()
import torch, open_clip
clip_model, _, clip_pre = open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')
clip_tok = open_clip.get_tokenizer('ViT-B-32')
PROMPTS_CHILD = ['a painting of a baby', 'a painting of a toddler', 'a painting of putti', 'a painting of cherubs',
                 'a painting of a winged cupid child', 'a painting of a small naked child', 'a painting of the infant Jesus']
PROMPTS_ADULT = ['a painting of a nude woman', 'a painting of a reclining nude woman', 'a painting of a nude man',
                 'a painting of women bathing', 'a painting of adult nudes', 'a painting of a woman', 'a painting of a man',
                 'a painting of a landscape', 'a painting of drapery', 'a painting of a crowd of adults']
with torch.no_grad():
    T = clip_model.encode_text(clip_tok(PROMPTS_CHILD + PROMPTS_ADULT)); T /= T.norm(dim=-1, keepdim=True)

def child_score(im):
    with torch.no_grad():
        x = clip_pre(im).unsqueeze(0)
        I = clip_model.encode_image(x); I /= I.norm(dim=-1, keepdim=True)
        p = (100 * I @ T.T).softmax(dim=-1)[0]
    return float(p[:len(PROMPTS_CHILD)].sum())

def has_child(im, foc):
    W, H = im.size
    crops = [im] + [im.crop((int(a * W), int(b * H), int((a + .6) * W), int((b + .6) * H))) for a in (0, .4) for b in (0, .4)]
    for f in foc:   # attorno a ogni genitale: il corpo a cui appartiene
        r = max(f['s'] * 3, 0.12)
        crops.append(im.crop((int(max(0, f['u'] - r * H / W) * W), int(max(0, f['v'] - r * 1.4) * H),
                              int(min(1, f['u'] + r * H / W) * W), int(min(1, f['v'] + r) * H))))
    return max(child_score(c) for c in crops if c.size[0] > 8 and c.size[1] > 8)

# ---------- il secondo occhio, quello che impara ----------
# Ogni notte: i punti trovati (e punti di pelle e di sfondo) diventano impronte CLIP, non immagini.
# Con quelle impronte si riaddestra un piccolo classificatore che rivede i casi incerti
# del modello di base. Da un dipinto scartato per possibili bambini non si impara mai niente.
import numpy as np
MEM_DIR = os.environ.get('SGUARDO_MEMORIA', '/tmp/sguardo-memoria')
os.makedirs(MEM_DIR, exist_ok=True)
MEM = os.path.join(MEM_DIR, 'memoria.npz')
OCCHIO = 'tools/sguardo-occhio.json'
occhio = load(OCCHIO, None)
W_learn = np.array(occhio['coef'], dtype=np.float32) if occhio else None
b_learn = occhio['b'] if occhio else 0.0
giro = (occhio or {}).get('giro', 0) + 1
try:
    _m = np.load(MEM); memX, memY = list(_m['X']), list(_m['y'])
except Exception:
    memX, memY = [], []
newX, newY = [], []

def embed(im, u, v, side):
    W, H = im.size
    r = side * H / 2
    c = im.crop((int(max(0, u * W - r)), int(max(0, v * H - r)), int(min(W, u * W + r)), int(min(H, v * H + r))))
    if c.size[0] < 8 or c.size[1] < 8: return None
    with torch.no_grad():
        e = clip_model.encode_image(clip_pre(c).unsqueeze(0)); e /= e.norm(dim=-1, keepdim=True)
    return e[0].numpy().astype(np.float32)

def learned(e):
    if W_learn is None or e is None: return None
    return float(1 / (1 + np.exp(-(e @ W_learn + b_learn))))

# ---------- l'inconscio: lo spazio latente ----------
VOC = []
for line in open('tools/sguardo-vocabolario.txt', encoding='utf-8'):
    line = line.strip()
    if line and not line.startswith('#') and '|' in line:
        it, en = line.split('|', 1); VOC.append((it.strip(), en.strip()))
with torch.no_grad():
    VE = clip_model.encode_text(clip_tok(['a painting of ' + en for _, en in VOC])); VE /= VE.norm(dim=-1, keepdim=True)
VE = VE.numpy().astype(np.float32)
# l'ovvio: quanto ogni parola somiglia a un corpo nudo dipinto qualsiasi. Si sottrae, per far affiorare il resto.
with torch.no_grad():
    _o = clip_model.encode_text(clip_tok(['a painting of a naked body', 'a painting of nude skin', 'a close-up of a painted nude']))
    _o /= _o.norm(dim=-1, keepdim=True)
OBVIOUS = (VE @ _o.numpy().astype(np.float32).T).mean(axis=1)
dreams = []          # associazioni del giorno, per il sogno della notte

def associate(e, k=6):
    if e is None: return [], []
    sims = VE @ e - 0.85 * OBVIOUS
    top = list(np.argsort(-sims)[:k])
    # deriva: dalla parola più vicina alla più vicina di quella, senza tornare indietro
    chain, cur, used = [], top[0], set()
    for _ in range(7):
        chain.append(VOC[cur][0]); used.add(cur)
        nb = VE @ VE[cur]
        nb[list(used)] = -9
        cur = int(np.argmax(nb + 0.04 * np.random.rand(len(nb))))
    return [VOC[i][0] for i in top], chain

def detect(im):
    W, H = im.size
    regions = [(0, 0, 1, 1)]
    regions += [(a, b, 0.55, 0.55) for a in (0, 0.45) for b in (0, 0.45)]
    regions += [(a, b, 0.4, 0.4) for a in (0, 0.3, 0.6) for b in (0, 0.3, 0.6)]
    regions += [(a, b, 0.25, 0.25) for a in (0, 0.25, 0.5, 0.75) for b in (0, 0.25, 0.5, 0.75)]
    out = []
    with tempfile.TemporaryDirectory() as td:
        for (a, b, w, h) in regions:
            box = (int(a * W), int(b * H), int((a + w) * W), int((b + h) * H))
            t = im.crop(box)
            if max(t.size) < 900:
                k = 900 / max(t.size); t = t.resize((int(t.size[0] * k), int(t.size[1] * k)), Image.LANCZOS)
            sx = (box[2] - box[0]) / t.size[0]; sy = (box[3] - box[1]) / t.size[1]
            pth = os.path.join(td, 't.jpg'); t.save(pth, quality=92)
            for d in det.detect(pth):
                if d['class'] not in KEEP or d['score'] < 0.05:      # anche i casi incerti: li rivede il secondo occhio
                    continue
                x, y, bw, bh = d['box']; x, y, bw, bh = x * sx, y * sy, bw * sx, bh * sy
                out.append({'u': round((box[0] + x + bw / 2) / W, 4), 'v': round((box[1] + y + bh / 2) / H, 4),
                            's': round(max(0.01, min(0.3, bh / H)), 4), 'k': KEEP[d['class']], 'sc': round(d['score'], 3)})
    out.sort(key=lambda f: -f['sc'])
    keep = []
    for f in out:
        if not any(((g['u'] - f['u']) ** 2 + (g['v'] - f['v']) ** 2) ** 0.5 < max(g['s'], f['s']) * 0.6 for g in keep):
            keep.append(f)
    return keep

def judge(im, props):
    """decide dove fermarsi; prepara gli esempi per l'apprendimento"""
    foc, ex, rej = [], [], []
    for f in props:
        e = embed(im, f['u'], f['v'], max(f['s'] * 2.2, 0.06))
        p = learned(e)
        nn = f['sc']
        ok = nn >= 0.25 or (p is not None and p >= 0.6 and nn >= 0.05) or (p is None and nn >= 0.15)
        if ok:
            g = dict(f); g['sc'] = round(max(nn, p or 0), 3); g['nn'] = nn
            if p is not None: g['p'] = round(p, 3)
            g['as'], g['catena'] = associate(e); g['av'] = 2
            dreams.append(g['as'])
            foc.append(g)
        elif nn >= 0.1:
            rej.append({'u': f['u'], 'v': f['v'], 's': f['s'], 'nn': nn, 'p': round(p, 3) if p is not None else None})
        if e is not None:
            if nn >= 0.4 or (p is not None and p >= 0.9 and nn >= 0.1): ex.append((e, 1))
            elif nn < 0.1 and (p is None or p < 0.2): ex.append((e, 0))
    for _ in range(6):    # punti a caso, lontani dai genitali: pelle e sfondo
        u, v = random.random(), random.random()
        if all(((u - f['u']) ** 2 + (v - f['v']) ** 2) ** 0.5 > max(f['s'] * 3, 0.08) for f in props):
            e = embed(im, u, v, random.uniform(0.05, 0.15))
            if e is not None: ex.append((e, 0))
    return foc, ex, rej

def skin(im):
    w = 48; h = max(6, round(48 * im.size[1] / im.size[0]))
    px = im.resize((w, h)).load()
    d, pts = [], []
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            sk = r > 90 and g > 40 and b > 20 and r > g and r > b and r - min(g, b) > 15 and abs(r - g) > 12
            d.append('1' if sk else '0')
            if sk: pts.append([round((x + .5) / w, 3), round((y + .5) / h, 3)])
    random.shuffle(pts)
    return {'w': w, 'h': h, 'd': ''.join(d)}, pts[:60]

def analyse(f, ii, year, source):
    raw = requests.get(ii['thumb'] or ii['url'], headers=UA, timeout=120).content
    im = Image.open(io.BytesIO(raw)).convert('RGB')
    W, H = im.size
    im = im.crop((int(W * CROP), int(H * CROP), int(W * (1 - CROP)), int(H * (1 - CROP))))
    props = detect(im)
    foc, ex, rej = judge(im, props)
    cs = has_child(im, foc + [p for p in props if p['sc'] >= 0.15])
    if cs <= 0.35:                       # impara solo da dipinti senza possibili bambini
        for e, y in ex: newX.append(e.astype(np.float16)); newY.append(y)
    grid, pts = skin(im)
    return {'f': f, 'y': year, 'src': source, 'v': VERSION, 'giro': giro, 'ii': ii, 'foc': foc, 'rej': rej[:6], 'grid': grid, 'skin': pts}, cs

# ---------- il giro ----------
budget = BUDGET
todo_cur = []
for w in works:
    e = next((atlas[n] for n in w['f'] if n in atlas), None)
    if e and e.get('v') == VERSION: continue
    todo_cur.append(w)
info = imageinfo([f for w in todo_cur for f in w['f']])
for w in todo_cur:
    if budget <= 0: break
    f = next((n for n in w['f'] if n in info and n not in esclusi), None)
    if not f: print('manca:', w['f'][0]); continue
    budget -= 1
    try:
        e, cs = analyse(f, info[f], w['y'], 'scelto')
        print(f'{f}: CLIP bambini {cs:.2f}')
        for n in w['f']: atlas.pop(n, None)
        atlas[f] = e
        print(f'{f}: {len(e["foc"])} genitali')
    except Exception as ex:
        print('errore', f, ex)
    time.sleep(1)

# l'occhio che ha imparato rilegge i dipinti più vecchi dell'atlante
old = sorted((e for e in atlas.values() if e.get('v') == VERSION), key=lambda e: e.get('giro', 0))[:min(12, budget)]
for e0 in old:
    if W_learn is None or e0.get('giro', 0) >= giro: break
    budget -= 1
    try:
        e, cs = analyse(e0['f'], e0['ii'], e0.get('y'), e0.get('src', 'pescato'))
        if e0.get('src') != 'scelto' and cs > 0.35:
            atlas.pop(e0['f']); scartati.add(e0['f']); print('riletto e scartato', e0['f']); continue
        print(f"riletto {e0['f']}: {len(e0['foc'])} -> {len(e['foc'])} genitali")
        atlas[e0['f']] = e
    except Exception as ex:
        print('errore', e0['f'], ex)
    time.sleep(1)

for e in list(atlas.values()):          # chi non ha ancora associazioni (o le ha vecchie): le riceve
    if not e.get('foc') or all(g.get('av') == 2 for g in e['foc']): continue
    try:
        raw = requests.get(e['ii']['thumb'] or e['ii']['url'], headers=UA, timeout=120).content
        im = Image.open(io.BytesIO(raw)).convert('RGB'); W, H = im.size
        im = im.crop((int(W * CROP), int(H * CROP), int(W * (1 - CROP)), int(H * (1 - CROP))))
        for g in e['foc']:
            g['as'], g['catena'] = associate(embed(im, g['u'], g['v'], max(g['s'] * 2.2, 0.06))); g['av'] = 2
            dreams.append(g['as'])
        print('associazioni per', e['f'], e['foc'][0]['as'][:3])
    except Exception as ex:
        print('errore associazioni', e['f'], ex)
    time.sleep(1)

for f, e in list(atlas.items()):      # pescati con una versione vecchia dell'analisi: via
    if e.get('src') != 'scelto' and e.get('v') != VERSION:
        atlas.pop(f)

if budget > 0 and len(atlas) < MAX_ATLAS:
    have = {e.get('q') for e in atlas.values() if e.get('q')}
    found = [t for t in discover() if t[0] not in atlas and t[0] not in scartati and t[0] not in esclusi and t[0] not in curated and t[2] not in have]
    random.shuffle(found)
    found = found[:budget * 2]
    meta = {t[0]: t for t in found}
    cand = [t[0] for t in found]
    info = imageinfo(cand)
    for f in cand:
        if budget <= 0: break
        if f not in info: scartati.add(f); continue
        budget -= 1
        try:
            e, cs = analyse(f, info[f], meta[f][1], 'pescato')
            e['q'] = meta[f][2]
            if cs > 0.35 or not e['foc']:
                scartati.add(f)
                motivi[f] = 'bambini' if cs > 0.35 else 'vuoto'
                print(f'scartato {f}: bambini {cs:.2f}, genitali {len(e["foc"])}')
                continue
            atlas[f] = e
            print(f'aggiunto {f}: {len(e["foc"])} genitali')
        except Exception as ex:
            print('errore', f, ex); scartati.add(f)
        time.sleep(1)

for f in esclusi: atlas.pop(f, None)
for f, e in list(atlas.items()):     # i filtri valgono anche per chi è già nell'atlante
    if e.get('src') != 'scelto' and CHILD_WORDS.search(f): atlas.pop(f); scartati.add(f)
res = list(atlas.values())
json.dump(res, open('sguardo/punti.json', 'w'), ensure_ascii=False, separators=(',', ':'))
json.dump(sorted(scartati), open('sguardo/scartati.json', 'w'), ensure_ascii=False, indent=0)
print('atlante:', len(res), 'con genitali:', sum(1 for r in res if r['foc']), 'scartati:', len(scartati))

# ---------- l'apprendimento della notte ----------
memX += newX; memY += newY
memX, memY = memX[-8000:], memY[-8000:]
np.savez_compressed(MEM, X=np.array(memX, dtype=np.float16), y=np.array(memY, dtype=np.int8))
y = np.array(memY)
print('memoria:', len(y), 'esempi, di cui genitali:', int(y.sum()) if len(y) else 0, '; nuovi stanotte:', len(newY))
if len(y) >= 40 and 0 < y.sum() < len(y):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    X = np.array(memX, dtype=np.float32)
    clf = LogisticRegression(C=2.0, class_weight='balanced', max_iter=3000)
    try:
        prec = round(float(cross_val_score(clf, X, y, cv=4).mean()), 3); print('precisione stimata:', prec)
    except Exception: prec = None
    clf.fit(X, y)
    json.dump({'giro': giro, 'esempi': int(len(y)), 'precisione': prec, 'coef': [round(float(c), 5) for c in clf.coef_[0]],
               'b': round(float(clf.intercept_[0]), 5)}, open(OCCHIO, 'w'))
    print('secondo occhio riaddestrato, giro', giro)
else:
    json.dump({'giro': giro, 'esempi': int(len(y)), 'coef': occhio['coef'] if occhio else None,
               'b': b_learn}, open(OCCHIO, 'w')) if occhio else None

# ---------- il sogno della notte: le associazioni del giorno, rimescolate ----------
sogno = []
pool_w = [w for a in dreams for w in a[:4]] or [w for e in atlas.values() for f in e.get('foc', []) for w in f.get('as', [])[:4]]
if pool_w:
    for _ in range(12):
        n = random.choice([2, 3, 3, 4, 5])
        line = []
        while len(line) < n:
            w = random.choice(pool_w)
            if w not in line: line.append(w)
            if len(set(pool_w)) < n: break
        sogno.append(' '.join(line))
print('sogno:', ' / '.join(sogno[:4]))

# ---------- quello che la voce può dire: dati veri di questa notte ----------
oc = load(OCCHIO, {}) or {}
json.dump({'giro': giro, 'esempi': int(len(y)), 'si': int(y.sum()) if len(y) else 0,
           'precisione': oc.get('precisione'), 'atlante': len(res), 'scartati': len(scartati),
           'motivi': dict(list(motivi.items())[-400:]), 'sogno': sogno},
          open('sguardo/voce.json', 'w'), ensure_ascii=False, separators=(',', ':'))
