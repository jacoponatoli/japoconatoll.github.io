#!/usr/bin/env python3
# Legge il feed RSS di Substack e riscrive blog/posts.js con gli articoli (dal più recente).
# Lo lancia da solo GitHub (vedi .github/workflows/blog.yml) ogni 3 ore; si può anche lanciare a mano.
import html, json, re, sys, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

FEED = "https://jacoponatoli.substack.com/feed"
OUT = "blog/posts.js"
MESI = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

def testo(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

def leggi(src):
    if src.startswith("http"):
        req = urllib.request.Request(src, headers={"User-Agent": "jacoponatoli.net blog updater"})
        return urllib.request.urlopen(req, timeout=30).read()
    return open(src, "rb").read()

def main(src=FEED):
    root = ET.fromstring(leggi(src))
    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
    posts = []
    for it in root.iter("item"):
        title = testo(it.findtext("title"))
        url = (it.findtext("link") or "").strip()
        if not title or not url:
            continue
        date = ""
        try:
            d = parsedate_to_datetime(it.findtext("pubDate"))
            date = "%d %s %d" % (d.day, MESI[d.month - 1], d.year)
        except Exception:
            pass
        ex = testo(it.findtext("description"))
        if not ex:
            ex = testo(it.findtext("content:encoded", namespaces=ns))
            if len(ex) > 220:
                ex = ex[:220].rsplit(" ", 1)[0] + "…"
        posts.append({"title": title, "date": date, "url": url, "excerpt": ex})
    body = "// Generato da tools/update-blog.py a partire da " + FEED + " (non modificare a mano)\nwindow.POSTS = " + json.dumps(posts, ensure_ascii=False, indent=1) + ";\n"
    old = open(OUT, encoding="utf-8").read() if __import__("os").path.exists(OUT) else ""
    if old != body:
        open(OUT, "w", encoding="utf-8").write(body)
        print("aggiornato:", len(posts), "articoli")
    else:
        print("nessuna novità")

if __name__ == "__main__":
    main(*sys.argv[1:])
