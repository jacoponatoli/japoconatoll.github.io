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
    q = ('SELECT DISTINCT ?img ?label WHERE { VALUES ?n { ' + ' '.join('wd:' + i for i in ids) + ' } '
         '?item wdt:P180 ?n ; wdt:P31 wd:Q3305213 ; wdt:P18 ?img . '
         'FILTER NOT EXISTS { VALUES ?c { ' + ' '.join('wd:' + i for i in kids) + ' } ?item wdt:P180 ?c } '
         'OPTIONAL { ?item rdfs:label ?label FILTER(LANG(?label)="en") } } LIMIT 6000')
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
        out.append(f)
    out = list(dict.fromkeys(out))
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
                if d['class'] not in KEEP or d['score'] < 0.15:
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
    foc = detect(im)
    cs = has_child(im, foc)
    grid, pts = skin(im)
    return {'f': f, 'y': year, 'src': source, 'v': VERSION, 'ii': ii, 'foc': foc, 'grid': grid, 'skin': pts}, cs

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

for f, e in list(atlas.items()):      # pescati con una versione vecchia dell'analisi: via
    if e.get('src') != 'scelto' and e.get('v') != VERSION:
        atlas.pop(f)

if budget > 0 and len(atlas) < MAX_ATLAS:
    cand = [f for f in discover() if f not in atlas and f not in scartati and f not in esclusi and f not in curated]
    random.shuffle(cand)
    cand = cand[:budget * 2]
    info = imageinfo(cand)
    for f in cand:
        if budget <= 0: break
        if f not in info: scartati.add(f); continue
        budget -= 1
        try:
            e, cs = analyse(f, info[f], None, 'pescato')
            if cs > 0.35 or not e['foc']:
                scartati.add(f)
                print(f'scartato {f}: bambini {cs:.2f}, genitali {len(e["foc"])}')
                continue
            atlas[f] = e
            print(f'aggiunto {f}: {len(e["foc"])} genitali')
        except Exception as ex:
            print('errore', f, ex); scartati.add(f)
        time.sleep(1)

for f in esclusi: atlas.pop(f, None)
res = list(atlas.values())
json.dump(res, open('sguardo/punti.json', 'w'), ensure_ascii=False, separators=(',', ':'))
json.dump(sorted(scartati), open('sguardo/scartati.json', 'w'), ensure_ascii=False, indent=0)
print('atlante:', len(res), 'con genitali:', sum(1 for r in res if r['foc']), 'scartati:', len(scartati))
