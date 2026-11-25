#!/usr/bin/env python3
"""AMBIENET — le poesie lette.
Prende poems.json (composto da tools/ambienet-poesia-compose.mjs con il compositore di POESIA LA NOTIZIA)
e fa leggere ogni poesia a una voce sintetica sempre diversa: uomini, donne, voci androgine tra i registri,
voci di bambine e bambini. Voce neurale (Piper, voci italiane paola e riccardo); se manca, espeak-ng.
Ogni voce cambia altezza, timbro, lentezza ed espressività. Salva un mp3 per poesia in out/ e out/index.json
con i versi e il momento in cui ognuno comincia, così AMBIENET mostra il verso mentre viene letto.
Tiene solo le ultime 48 poesie. Alla fine fa preparare anche le domande (ambienet-domande.py)."""
import json, os, random, subprocess, wave, io, hashlib, datetime, struct

OUT = 'out'; os.makedirs(OUT, exist_ok=True)
MODELS = {'paola': 'voices/it_IT-paola-medium.onnx', 'riccardo': 'voices/it_IT-riccardo-x_low.onnx'}
# nome mostrato, voce di partenza, semitoni (altezza e timbro), lentezza, peso
PROFILES = [
    ('voce di uomo', 'riccardo', (-1, 1), (1.05, 1.3), 1.2),
    ('voce di uomo, grave', 'riccardo', (-4, -2), (1.15, 1.4), .8),
    ('voce di donna', 'paola', (-1, 1), (1.05, 1.3), 1.2),
    ('voce di donna, chiara', 'paola', (1, 3), (1.0, 1.25), .8),
    ('voce androgina', 'riccardo', (3, 5), (1.05, 1.3), 1.0),
    ('voce androgina', 'paola', (-5, -3), (1.05, 1.3), 1.0),
    ('voce tra i registri', 'paola', (-2, 0), (1.05, 1.3), .9),   # AMBIENET la fa scivolare tra grave e acuto
    ('voce di bambina', 'paola', (6, 8), (.95, 1.15), 1.6),
    ('voce di bambino', 'riccardo', (8, 10), (.95, 1.15), 1.4),
    ('voci di bambini', 'paola', (6, 9), (.95, 1.15), 1.6),          # AMBIENET ne fa un piccolo coro
]
voices = {}
try:
    from piper.voice import PiperVoice
    for k, p in MODELS.items():
        if os.path.exists(p): voices[k] = PiperVoice.load(p, config_path=p + '.json')
except Exception as e:
    print('piper non disponibile:', e)

def frames_piper(v, text, ls, ns, nw):
    b = io.BytesIO()
    with wave.open(b, 'wb') as wf: v.synthesize(text, wf, length_scale=ls, noise_scale=ns, noise_w=nw)
    b.seek(0)
    with wave.open(b, 'rb') as rf: return rf.getframerate(), rf.readframes(rf.getnframes())

def frames_espeak(text, prof, ls):
    var = {'paola': random.choice(['f2', 'f3', 'f4']), 'riccardo': random.choice(['m1', 'm3', 'm6'])}[prof[1]]
    subprocess.run(['espeak-ng', '-v', f'it+{var}', '-s', str(int(150 / ls)), '-p', '45', '-w', 'v.wav', text], check=True)
    with wave.open('v.wav', 'rb') as rf: return rf.getframerate(), rf.readframes(rf.getnframes())

def render(poem, path):
    prof = random.choices(PROFILES, weights=[p[4] for p in PROFILES])[0]
    semi = random.uniform(*prof[2]); ls = random.uniform(*prof[3])
    ns, nw = random.uniform(.6, .95), random.uniform(.7, 1.0)   # espressività: ogni lettura diversa
    sr, pcm, times, t = None, b'', [], 0.0
    lines = poem['lines'] + ([] if not poem.get('title') else [])
    if poem.get('title'): lines = [poem['title'], ''] + poem['lines']
    for ln in lines:
        if not ln:
            gap = random.uniform(1.2, 1.9)
        else:
            v = voices.get(prof[1])
            r, fr = frames_piper(v, ln, ls, ns, nw) if v else frames_espeak(ln, prof, ls)
            if sr is None: sr = r
            times.append(round(t, 2)); pcm += fr; t += len(fr) / 2 / sr
            gap = random.uniform(.45, .95)
        if sr: pcm += b'\x00\x00' * int(gap * sr); t += gap
    with wave.open('raw.wav', 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr); wf.writeframes(pcm)
    f = 2 ** (semi / 12)   # altezza e timbro insieme, durata invariata
    af = f'asetrate={int(sr * f)},aresample=44100,atempo={1 / f:.4f},highpass=f=70,loudnorm=I=-20:TP=-2'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', 'raw.wav', '-af', af, '-ac', '1', '-b:a', '48k', path], check=True)
    return prof[0], times, round(t, 1), ('piper' if voices.get(prof[1]) else 'espeak')

poems = json.load(open('poems.json', encoding='utf-8'))
idx = {'items': []}
if os.path.exists(f'{OUT}/index.json'):
    try: idx = json.load(open(f'{OUT}/index.json', encoding='utf-8'))
    except Exception: pass
stamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ')
for p in poems:
    h = hashlib.sha1(json.dumps(p, ensure_ascii=False).encode()).hexdigest()[:12]
    try:
        name, times, dur, eng = render(p, f'{OUT}/{h}.mp3')
    except Exception as e:
        print('errore', e); continue
    shown = ([p['title'], ''] if p.get('title') else []) + p['lines']
    idx['items'].insert(0, {'f': f'{h}.mp3', 'form': p['name'], 'voice': name, 'engine': eng, 'lines': [l for l in shown if l], 'times': times, 'dur': dur, 'made': stamp})
    print(p['name'], '·', name, '·', dur, 's')
idx['items'] = idx['items'][:48]
keep = {it['f'] for it in idx['items']}
for fn in os.listdir(OUT):
    if fn.endswith('.mp3') and fn not in keep: os.remove(f'{OUT}/{fn}')
idx['updated'] = stamp
json.dump(idx, open(f'{OUT}/index.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# le domande: una voce di macchina che interroga chi ascolta (tools/ambienet-domande.py, in out/q/)
import sys
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ambienet-domande.py')], check=False)
