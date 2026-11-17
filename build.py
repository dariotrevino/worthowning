"""Builds index.html from products.json and src/page.html.

Run:  python3 build.py
Edit products.json to add, remove or change picks, then run this again.
"""
import datetime, html, json, re

SITE = "https://worthowning.net/"

data = json.load(open("products.json", encoding="utf-8"))
page = open("src/page.html", encoding="utf-8").read()
TAG = data.get("amazon_tag", "")
cats = {c["id"]: c["label"] for c in data["categories"]}
ARROW = ('<span class="out" aria-hidden="true"><svg viewBox="0 0 10 10" width="10" height="10">'
         '<path d="M2 8 8 2M3.2 2H8v4.8" fill="none" stroke="currentColor" stroke-width="1.2"/></svg></span>')

def is_amazon(url):
    return re.match(r"^https://(www\.)?amazon\.com/", url or "") is not None

def money(p):
    v = p["price"]
    s = "${:,.0f}".format(v) if float(v).is_integer() else "${:,.2f}".format(v)
    return ("from " if p.get("from") else "") + s

def name_html(text):
    # Keeps model numbers such as KS-203 from splitting across lines.
    out = []
    for w in text.split(" "):
        e = html.escape(w)
        out.append('<span class="nb">%s</span>' % e if "-" in w else e)
    return " ".join(out)

def image_size(path):
    # Reads width and height from a WebP header so the browser can reserve space.
    try:
        b = open(path, "rb").read(30)
        if b[12:16] == b"VP8X":
            return 1 + int.from_bytes(b[24:27], "little"), 1 + int.from_bytes(b[27:30], "little")
        if b[12:16] == b"VP8 ":
            return int.from_bytes(b[26:28], "little") & 0x3FFF, int.from_bytes(b[28:30], "little") & 0x3FFF
        if b[12:16] == b"VP8L":
            v = int.from_bytes(b[21:25], "little")
            return (v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1
    except OSError:
        pass
    return 0, 0

def card(p):
    e = html.escape
    url = p.get("url") or ""
    paid = bool(p.get("affiliate"))
    if TAG and is_amazon(url):
        url += ("&" if "?" in url else "?") + "tag=" + TAG
        paid = True
    if p.get("image"):
        w, h = image_size(p["image"])
        dims = ' width="%d" height="%d"' % (w, h) if w else ""
        lazy = ' loading="lazy"' if card.n >= 6 else ""
        card.n += 1
        art = '<img src="%s" alt="%s"%s%s decoding="async">' % (
            e(p["image"]), e(p["brand"] + " " + p["name"]), dims, lazy)
        art_cls = "art photo"
    else:
        art = '<span class="tile-mono">%s</span>' % ("?" if p.get("pending") else e(p["brand"][0]))
        art_cls = "art"
    meta = e(p["brand"]) + (" · " + e(cats[p["cat"]]) if p.get("cat") else "")
    price = '<p class="price">%s</p>' % money(p) if p.get("price") is not None else ""
    inner = ('<div class="%s" aria-hidden="true">%s</div>%s<div class="info"><p class="meta">%s</p>'
             '<div class="row"><h3 class="name">%s</h3>%s</div></div>%s') % (
        art_cls, art, ARROW if url else "", meta, name_html(p["name"]), price,
        '<span class="sr-only">View at %s</span>' % e(p["store"]) if url else "")
    if url:
        rel = "sponsored nofollow noopener" if paid else "noopener"
        body = '<a class="card" href="%s" rel="%s">%s</a>' % (e(url), rel, inner)
    else:
        body = '<div class="card">%s</div>' % inner
    return '<li data-cat="%s" data-tags="%s" data-price="%s"%s>%s</li>' % (
        e(p.get("cat") or ""), e(" ".join(p.get("tags", []))),
        "" if p.get("price") is None else p["price"], " data-yours" if p.get("yours") else "", body)

def tab(fid, label, on=False):
    return '<button class="tab" type="button" data-filter="%s" aria-pressed="%s">%s</button>' % (
        fid, "true" if on else "false", html.escape(label))

card.n = 0
# Placeholders still waiting on a name stay out of the public page.
live = [p for p in data["products"] if not p.get("pending")]

tabs = [tab("all", "All", True), tab("yours", "Your picks")]
tabs += [tab(t["id"], t["label"]) for t in data["tags"]]
tabs.append('<span class="sep" aria-hidden="true"></span>')
tabs += [tab(c["id"], c["label"]) for c in data["categories"]]

page = page.replace("{{TABS}}", "".join(tabs))
page = page.replace("{{GRID}}", "\n      " + "\n      ".join(card(p) for p in live) + "\n    ")
page = page.replace("{{AMAZON_HIDDEN}}", "" if TAG else " hidden")
GA = data.get("ga_id", "")
ga = ('<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>\n'
      '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}'
      'gtag("js",new Date());gtag("config","%s");</script>\n') % (GA, GA) if GA else ""
page = page.replace("{{ANALYTICS}}", ga)
schema = {
    "@context": "https://schema.org",
    "@graph": [
        {"@type": "WebSite", "@id": SITE + "#website", "url": SITE, "name": "Worth Owning",
         "inLanguage": "en-US", "publisher": {"@id": SITE + "#org"}},
        {"@type": "Organization", "@id": SITE + "#org", "name": "Worth Owning", "url": SITE,
         "logo": SITE + "apple-touch-icon.png"},
        {"@type": "CollectionPage", "@id": SITE + "#page", "url": SITE,
         "name": "Worth Owning · Buy it for life gear, Japanese tools and stainless steel",
         "isPartOf": {"@id": SITE + "#website"},
         "mainEntity": {"@type": "ItemList", "numberOfItems": len(live), "itemListElement": [
             {"@type": "ListItem", "position": i + 1, "name": p["brand"] + " " + p["name"]}
             for i, p in enumerate(live)]}},
    ],
}
page = page.replace("{{SCHEMA}}", '<script type="application/ld+json">%s</script>' %
                    json.dumps(schema, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
open("index.html", "w", encoding="utf-8").write(page)

today = datetime.date.today().isoformat()
open("sitemap.xml", "w", encoding="utf-8").write(
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    '  <url><loc>%s</loc><lastmod>%s</lastmod></url>\n'
    '</urlset>\n' % (SITE, today))
open("robots.txt", "w", encoding="utf-8").write(
    "User-agent: *\nAllow: /\n\nSitemap: %ssitemap.xml\n" % SITE)
print("Built index.html with %d picks (%d pending, hidden)" % (len(live), len(data["products"]) - len(live)))
