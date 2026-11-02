#!/usr/bin/env python3
"""SLOPOLS — il mare.

Ogni ora scorre i video pubblicati su Civitai (i più nuovi, e a turno sempre più in profondità
nell'archivio dei più visti), guarda l'anteprima di ciascuno con CLIP e tiene solo quelli in cui
si vede il mare, o almeno acqua, liquido. L'elenco cresce in DATA/sea.json, che la pagina
slopols/ legge. Uso: slopols-sea.py DATA_DIR
"""
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

DATA = sys.argv[1] if len(sys.argv) > 1 else "data"
API = "https://civitai.com/api/v1/images"
UA = {"User-Agent": "Mozilla/5.0 (SLOPOLS; jacoponatoli.net)"}
MAX_CAND = int(os.environ.get("MAX_CAND", "3000"))
DIG_PAGES = int(os.environ.get("DIG_PAGES", "8"))
KEEP = 6000

# what CLIP is asked: the sea first, then water and liquids, against everything else slop is made of
POS_SEA = ["the open sea", "ocean waves", "a stormy sea with huge waves", "an underwater scene in the ocean",
           "waves breaking on a beach", "a ship sailing on the ocean", "the sea at sunset", "a coral reef underwater",
           "a sea creature swimming in the ocean", "a tsunami wave"]
POS_WATER = ["the surface of water with ripples", "flowing liquid", "a waterfall", "a river", "rain falling on water",
             "a big splash of water", "a flooded city", "a person swimming in water", "a liquid pouring"]
NEG = ["a portrait of a person", "a person dancing", "people inside a room", "a city street", "a car on a road",
       "an animal on grass", "food on a table", "a cartoon character", "a forest", "a desert", "a blue sky with clouds",
       "snowy mountains", "text and a logo", "a fantasy monster", "a video game scene", "fire and flames",
       "outer space with stars", "a woman posing for the camera", "a man talking to the camera", "a robot",
       "a building", "a bedroom", "a toy", "a glass of drink on a table", "a fish tank in a room",
       "a close-up portrait of a face", "a person in a uniform", "a cartoon animal character", "an anime girl",
       "a clown", "a close-up of an eye", "hands painting on a canvas", "a spiral pattern",
       "a product on a plain background", "a plant or a flower", "a person riding a bicycle", "a costume character"]
CRIT = 3   # version of the criteria: when it changes, the whole archive is judged again
LABELS = POS_SEA + POS_WATER + NEG
NS, NW = len(POS_SEA), len(POS_WATER)
SEA_WORDS = re.compile(r"\b(seas?|ocean|oceans|waves|surf|tide|tsunami|seashore|shore|underwater|undersea|reef|"
                       r"coral|sailing|ship|shipwreck|whale|mare|oceano|onde)\b|海|浪", re.I)


def load(name, default):
    try:
        with open(os.path.join(DATA, name)) as f:
            return json.load(f)
    except Exception:
        return default


def save(name, obj):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, name), "w") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def page(params=None, url=None):
    url = url or API + "?" + urllib.parse.urlencode(params)
    for k in range(3):
        try:
            return json.loads(get(url))
        except Exception as e:
            print("  pagina non letta:", str(e)[:80])
            time.sleep(3 + 3 * k)
    return {}


state = load("state.json", {"cursors": {}, "seen": [], "runs": 0})
sea = load("sea.json", [])
seen = set(state["seen"]) | {e["id"] for e in sea}
cand = []
if state.get("crit") != CRIT and sea:          # new criteria: the archive goes back under CLIP's eye
    cand = [{"id": e["id"], "url": e["alt"], "thumbnail": {"url": e["th"]}, "meta": {"prompt": e.get("p", "")},
             "hash": e.get("bh"), "baseModel": e.get("m"), "createdAt": e.get("t", "")} for e in sea]
    print("archivio da rivedere con i criteri", CRIT, ":", len(cand))
    sea = []
MAX_CAND += len(cand)


def collect(j):
    n = 0
    for i in j.get("items", []):
        if len(cand) >= MAX_CAND:
            break
        if i.get("type") != "video" or i.get("nsfwLevel") != "None" or i["id"] in seen:
            continue
        th = (i.get("thumbnail") or {}).get("url")
        if not th or not i.get("url"):
            continue
        seen.add(i["id"])
        cand.append(i)
        n += 1
    return n


base = {"limit": 100, "nsfw": "None", "type": "video", "withMeta": "true"}

# 1. the new generations, until a page brings nothing new
url = None
for _ in range(12):
    j = page({**base, "sort": "Newest"}, url)
    got = collect(j)
    url = (j.get("metadata") or {}).get("nextPage")
    if not got or not url:
        break
print("nuove generazioni da guardare:", len(cand))

# 2. digging, a little deeper every run, in turn through the most watched of every period
combos = [(s, p) for s in ("Most Reactions", "Most Comments", "Most Collected")
          for p in ("AllTime", "Year", "Month", "Week", "Day")]
r = state.get("runs", 0)
for k in range(3):
    s, p = combos[(r * 3 + k) % len(combos)]
    key = s + "|" + p
    url = state["cursors"].get(key)
    for _ in range(DIG_PAGES):
        if len(cand) >= MAX_CAND:
            break
        j = page({**base, "sort": s, "period": p}, url)
        collect(j)
        url = (j.get("metadata") or {}).get("nextPage")
        if not url:
            break
    state["cursors"][key] = url
print("da guardare in tutto:", len(cand))


def thumb(i):
    try:
        im = Image.open(io.BytesIO(get(i["thumbnail"]["url"], 25))).convert("RGB")
        im.thumbnail((336, 336))
        return im
    except Exception:
        return None


torch.set_num_threads(os.cpu_count() or 2)
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval()
proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
TXT = proc(text=["a frame from a video of " + l for l in LABELS], return_tensors="pt", padding=True)



def water_window(im):
    """Where is the sea in the frame? CLIP looks at 18 crops and the most watery one is where the page zooms."""
    W, H = im.size
    boxes = []
    for f, n in ((.5, 3), (1 / 3, 3)):
        for gy in range(n):
            for gx in range(n):
                cx = f / 2 + gx * (1 - f) / (n - 1)
                cy = f / 2 + gy * (1 - f) / (n - 1)
                boxes.append((cx, cy, f))
    crops = [im.crop((int((cx - f / 2) * W), int((cy - f / 2) * H), int((cx + f / 2) * W), int((cy + f / 2) * H)))
             for cx, cy, f in boxes]
    with torch.no_grad():
        x = proc(images=crops, return_tensors="pt")
        out = model(input_ids=TXT["input_ids"], attention_mask=TXT["attention_mask"], pixel_values=x["pixel_values"])
        P = out.logits_per_image.softmax(dim=-1).tolist()
    sc = [sum(p[:NS + NW]) for p in P]
    k = max(range(len(sc)), key=lambda i: sc[i] + (.04 if boxes[i][2] > .4 else 0))
    if sc[k] < .5:
        return [.5, .5, 1]
    cx, cy, f = boxes[k]
    return [round(cx, 3), round(cy, 3), round(min(2.6, 1 / f), 2)]


found, near = [], []
with ThreadPoolExecutor(16) as ex:
    for b in range(0, len(cand), 32):
        batch = cand[b:b + 32]
        ims = list(ex.map(thumb, batch))
        ok = [(i, im) for i, im in zip(batch, ims) if im is not None]
        if not ok:
            continue
        with torch.no_grad():
            x = proc(images=[im for _, im in ok], return_tensors="pt")
            out = model(input_ids=TXT["input_ids"], attention_mask=TXT["attention_mask"], pixel_values=x["pixel_values"])
            P = out.logits_per_image.softmax(dim=-1)
        for (i, im), pr in zip(ok, P.tolist()):
            ps, pw = sum(pr[:NS]), sum(pr[NS:NS + NW])
            prompt = ((i.get("meta") or {}).get("prompt") or "").strip()
            bonus = .15 if SEA_WORDS.search(prompt) else 0
            top = max(range(len(LABELS)), key=lambda k: pr[k])
            strong = top < NS + NW          # the best description of the frame must be sea or water
            entry = {"id": i["id"], "src": i["url"].replace("/original=true/", "/transcode=true,width=720/"),
                     "alt": i["url"], "p": prompt[:600], "bh": i.get("hash"), "th": i["thumbnail"]["url"],
                     "k": "mare" if ps >= pw else "acqua", "s": round(ps + pw, 3), "l": LABELS[top],
                     "ps": round(ps, 3),
                     "m": i.get("baseModel"), "t": (i.get("createdAt") or "")[:10]}
            if strong and (ps + bonus >= .55 or (pw >= .7 and ps + pw >= .78)):
                entry["z"] = water_window(im)
                found.append(entry)
            elif ps + pw >= .3:
                near.append(entry)
        print(f"  {min(b + 32, len(cand))}/{len(cand)} guardati, mare/acqua trovati: {len(found)}", flush=True)

print("\nTROVATI", len(found))
for e in sorted(found, key=lambda e: -e["s"])[:15]:
    print(f"  {e['s']:.2f} {e['k']:5} {e['l'][:34]:34} {e['p'][:60]!r}")
print("SCARTATI PER POCO", len(near))
for e in sorted(near, key=lambda e: -e["s"])[:10]:
    print(f"  {e['s']:.2f} {e['k']:5} {e['l'][:34]:34} {e['p'][:60]!r}")

hashes, merged = set(), []
for e in sorted(sea + found, key=lambda e: -e["id"]):      # the same picture posted twice counts once
    if e.get("bh") and e["bh"] in hashes:
        continue
    hashes.add(e.get("bh"))
    merged.append(e)
sea = merged[:KEEP]
state["crit"] = CRIT
state["seen"] = sorted(seen)[-80000:]
state["runs"] = r + 1
state["last"] = time.strftime("%Y-%m-%d %H:%M", time.gmtime())
save("sea.json", sea)
save("state.json", state)
print("archivio del mare:", len(sea), "video  ·  mare:", sum(e["k"] == "mare" for e in sea),
      " acqua:", sum(e["k"] == "acqua" for e in sea))
