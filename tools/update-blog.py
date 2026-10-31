#!/usr/bin/env python3
# Legge il feed RSS di Substack e riscrive blog/posts.js con gli articoli (dal più recente).
# Lo lancia da solo GitHub (vedi .github/workflows/blog.yml) ogni 3 ore; si può anche lanciare a mano.
import html, json, os, re, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

FEED = "https://jacoponatoli.substack.com/feed"
OUT = "blog/posts.js"
LOCALI = "blog/locali.json"
MESI = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

def quando(p):
    # "19 October 2026" -> (2026, 10, 19), per mettere gli articoli dal più recente
    try:
        g, m, a = p.get("date", "").split()
        return (int(a), MESI.index(m) + 1, int(g))
    except Exception:
        return (0, 0, 0)

def testo(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"}
# Substack a volte blocca i server di GitHub: in quel caso si passa da servizi che leggono il feed per noi
VIE = [
    lambda u: u,
    lambda u: "https://api.allorigins.win/raw?url=" + urllib.parse.quote(u, safe=""),
    lambda u: "https://corsproxy.io/?url=" + urllib.parse.quote(u, safe=""),
    lambda u: "https://r.jina.ai/" + u,
]

def leggi(src):
    if not src.startswith("http"):
        return open(src, "rb").read()
    errori = []
    for via in VIE:
        url = via(src)
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
            i = raw.find(b"<rss")
            if i < 0:
                raise ValueError("risposta senza <rss>")
            print("feed letto da:", url.split("/")[2])
            return raw[i:]
        except Exception as e:
            errori.append("%s → %s" % (url.split("/")[2], str(e)[:80]))
    raise IOError("; ".join(errori))

def main(src=FEED):
    raw = leggi(src)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise ValueError("il feed non è XML (forse nessun articolo pubblicato ancora): " + raw[:120].decode("utf-8", "replace"))
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
        # se l'articolo ha anche una pagina sul sito (blog/<slug>/index.html), il blog punta a quella
        slug = urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1]
        if slug and os.path.exists(os.path.join("blog", slug, "index.html")):
            url = slug + "/"
        posts.append({"title": title, "date": date, "url": url, "excerpt": ex})
    # articoli pubblicati solo sul sito (non su Substack): stanno in blog/locali.json
    # se poi lo stesso articolo esce anche su Substack con lo stesso slug, resta una voce sola
    if os.path.exists(LOCALI):
        presenti = {p["url"] for p in posts}
        for p in json.load(open(LOCALI, encoding="utf-8")):
            if p.get("url") not in presenti:
                posts.append({"title": p["title"], "date": p.get("date", ""), "url": p["url"], "excerpt": p.get("excerpt", "")})
    posts.sort(key=quando, reverse=True)
    body = "// Generato da tools/update-blog.py a partire da " + FEED + " (non modificare a mano)\nwindow.POSTS = " + json.dumps(posts, ensure_ascii=False, indent=1) + ";\n"
    old = open(OUT, encoding="utf-8").read() if __import__("os").path.exists(OUT) else ""
    if old != body:
        open(OUT, "w", encoding="utf-8").write(body)
        print("aggiornato:", len(posts), "articoli")
    else:
        print("nessuna novità")

if __name__ == "__main__":
    try:
        main(*sys.argv[1:])
    except Exception as e:
        # niente panico: la pagina resta com'è; il messaggio compare come avviso su GitHub
        print("::warning::Feed Substack non letto: %s: %s" % (type(e).__name__, str(e)[:300]))
