# SGUARDO — analisi fatta una volta sola (da GitHub Actions), non nel browser dei visitatori.
# Per ogni dipinto di sguardo/opere.json: prende l'immagine da Wikimedia Commons, trova i genitali
# con NudeNet (intero + riquadri, per i corpi piccoli), calcola la mappa della pelle,
# e scrive tutto in sguardo/punti.json. La pagina legge solo quel file.
import json, os, sys, time, tempfile, io
import requests
from PIL import Image
from nudenet import NudeDetector

UA = {'User-Agent': 'SGUARDO/1.0 (https://jacoponatoli.net/sguardo/) python-requests'}
CROP = 0.03
KEEP = {'FEMALE_GENITALIA_EXPOSED': 'vulva', 'MALE_GENITALIA_EXPOSED': 'pene',
        'FEMALE_GENITALIA_COVERED': 'vulva coperta', 'ANUS_EXPOSED': 'ano'}
works = json.load(open('sguardo/opere.json'))
files = [f for w in works for f in w['f']]

info = {}
for i in range(0, len(files), 40):
    r = requests.get('https://commons.wikimedia.org/w/api.php', headers=UA, timeout=60, params={
        'action': 'query', 'format': 'json', 'prop': 'imageinfo', 'iiprop': 'size|url|mime',
        'iiurlwidth': 1920, 'titles': '|'.join('File:' + f for f in files[i:i + 40])}).json()
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

det = None
try:   # modello più grande e preciso, se scaricabile
    p640 = '/tmp/640m.onnx'
    if not os.path.exists(p640):
        r = requests.get('https://github.com/notAI-tech/NudeNet/releases/download/v3.4-weights/640m.onnx', timeout=120)
        r.raise_for_status(); open(p640, 'wb').write(r.content)
    det = NudeDetector(model_path=p640, inference_resolution=640)
    print('modello 640m')
except Exception as e:
    print('modello 640m non disponibile:', e)
    det = NudeDetector()

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
            if max(t.size) < 900:   # i riquadri piccoli si ingrandiscono: corpi piccoli più visibili
                f = 900 / max(t.size); t = t.resize((int(t.size[0] * f), int(t.size[1] * f)), Image.LANCZOS)
            sx = (box[2] - box[0]) / t.size[0]; sy = (box[3] - box[1]) / t.size[1]
            pth = os.path.join(td, 't.jpg'); t.save(pth, quality=92)
            for d in det.detect(pth):
                if d['class'] not in KEEP or d['score'] < 0.15:
                    continue
                x, y, bw, bh = d['box']
                x, y, bw, bh = x * sx, y * sy, bw * sx, bh * sy
                u = (box[0] + x + bw / 2) / W; v = (box[1] + y + bh / 2) / H
                out.append({'u': round(u, 4), 'v': round(v, 4), 's': round(max(0.01, min(0.3, bh / H)), 4),
                            'k': KEEP[d['class']], 'sc': round(d['score'], 3)})
    out.sort(key=lambda f: -f['sc'])
    keep = []
    for f in out:
        if not any(((g['u'] - f['u']) ** 2 + (g['v'] - f['v']) ** 2) ** 0.5 < max(g['s'], f['s']) * 0.6 for g in keep):
            keep.append(f)
    return keep

def skin(im):
    w = 96; h = max(8, round(96 * im.size[1] / im.size[0]))
    px = im.resize((w, h)).load()
    d, pts = [], []
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            sk = r > 90 and g > 40 and b > 20 and r > g and r > b and r - min(g, b) > 15 and abs(r - g) > 12
            d.append('1' if sk else '0')
            if sk and x % 2 and y % 2:
                pts.append([round(x / w, 3), round(y / h, 3)])
    return {'w': w, 'h': h, 'd': ''.join(d)}, pts

res = []
for w in works:
    f = next((n for n in w['f'] if n in info), None)
    if not f:
        print('manca:', w['f'][0]); continue
    ii = info[f]
    try:
        raw = requests.get(ii['thumb'] or ii['url'], headers=UA, timeout=120).content
        im = Image.open(io.BytesIO(raw)).convert('RGB')
        W, H = im.size
        im = im.crop((int(W * CROP), int(H * CROP), int(W * (1 - CROP)), int(H * (1 - CROP))))
        foc = detect(im)
        grid, pts = skin(im)
        res.append({'f': f, 'y': w['y'], 'ii': ii, 'foc': foc, 'grid': grid, 'skin': pts[:120]})
        print(f'{f}: {len(foc)} genitali')
    except Exception as e:
        print('errore', f, e)
    time.sleep(1.5)

json.dump(res, open('sguardo/punti.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('dipinti:', len(res), 'con genitali:', sum(1 for r in res if r['foc']))
