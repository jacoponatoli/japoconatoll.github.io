#!/usr/bin/env python3
"""AMBIENET — la voce degli slogan.
Legge TUTTI gli slogan di SLOGAN (slogan/corpo.json: quelli inventati e quelli letti nelle piazze),
li fa dire a una voce sintetica robotica (espeak-ng) e salva un mp3 per slogan in out/,
con out/index.json. Gli slogan già letti non vengono rifatti; nessuno viene tolto.
AMBIENET li ascolta poi dal ramo "ambienet-voice", lontani, filtrati e riverberati."""
import json, os, re, random, hashlib, subprocess, datetime

OUT = 'out'
os.makedirs(OUT, exist_ok=True)
corpo = json.load(open('slogan/corpo.json', encoding='utf-8'))

texts = []
for key in ('slogan', 'letti'):
    for g in corpo.get(key, []):
        for t in g.get('t', []):
            t = re.sub(r'\s+', ' ', str(t)).strip()
            if t and t not in texts:
                texts.append(t)

EN = re.compile(r"\b(the|and|not|is|are|our|we|you|no|over|for|of|to|out|go|away|tax|kings|make|whose|streets|rich|empire|democracy)\b", re.I)
IT = re.compile(r"\b(il|lo|la|le|gli|non|di|del|della|che|per|più|meno|noi|siamo|nessun|anche|anche|un|una|ai|alle|è)\b", re.I)
def lang_of(t):
    return 'en' if len(EN.findall(t)) > len(IT.findall(t)) else 'it'

VOICE = {'it': 'it', 'en': 'en-us'}
VARIANTS = ['robosoft', 'robosoft2', 'robosoft3', 'm3', 'm7', 'klatt3', 'croak']

old = {}
if os.path.exists(f'{OUT}/index.json'):
    try:
        for it in json.load(open(f'{OUT}/index.json', encoding='utf-8')).get('items', []):
            old[it['t']] = it
    except Exception:
        pass

def render(t, lang, path):
    base = ['espeak-ng', '-s', str(random.randint(105, 135)), '-p', str(random.randint(12, 40)), '-g', '6', '-w', 'tmp.wav']
    for v in (f"{VOICE[lang]}+{random.choice(VARIANTS)}", VOICE[lang]):
        try:
            subprocess.run(base[:1] + ['-v', v] + base[1:] + [t], check=True, capture_output=True)
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', 'tmp.wav', '-ac', '1', '-ar', '22050', '-b:a', '40k', path], check=True)
            return True
        except Exception as e:
            print('  retry without variant:', e)
    return False

items, new = [], 0
for t in texts:
    if t in old and os.path.exists(f"{OUT}/{old[t]['f']}"):
        items.append(old[t]); continue
    lang = lang_of(t)
    f = hashlib.sha1((lang + t).encode()).hexdigest()[:12] + '.mp3'
    if render(t, lang, f'{OUT}/{f}'):
        items.append({'f': f, 't': t, 'lang': lang}); new += 1
if os.path.exists('tmp.wav'):
    os.remove('tmp.wav')
json.dump({'updated': datetime.datetime.utcnow().isoformat(timespec='seconds') + 'Z', 'items': items},
          open(f'{OUT}/index.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(f'{len(items)} slogan, {new} nuovi')
