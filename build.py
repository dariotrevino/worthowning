"""Builds index.html from products.json and src/page.html.

Run:  python3 build.py
Edit products.json to add, remove or change picks, then run this again.
"""
import html, json, re

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

def card(p):
    e = html.escape
    url = p.get("url") or ""
    paid = bool(p.get("affiliate"))
    if TAG and is_amazon(url):
        url += ("&" if "?" in url else "?") + "tag=" + TAG
        paid = True
    if p.get("image"):
        art = '<img src="%s" alt="">' % e(p["image"])
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
    return '<li data-cat="%s" data-tags="%s"%s>%s</li>' % (
        e(p.get("cat") or ""), e(" ".join(p.get("tags", []))), " data-yours" if p.get("yours") else "", body)

def tab(fid, label, on=False):
    return '<button class="tab" type="button" data-filter="%s" aria-pressed="%s">%s</button>' % (
        fid, "true" if on else "false", html.escape(label))

tabs = [tab("all", "All", True), tab("yours", "Your picks")]
tabs += [tab(t["id"], t["label"]) for t in data["tags"]]
tabs.append('<span class="sep" aria-hidden="true"></span>')
tabs += [tab(c["id"], c["label"]) for c in data["categories"]]

page = page.replace("{{TABS}}", "".join(tabs))
page = page.replace("{{GRID}}", "\n      " + "\n      ".join(card(p) for p in data["products"]) + "\n    ")
page = page.replace("{{AMAZON_HIDDEN}}", "" if TAG else " hidden")
open("index.html", "w", encoding="utf-8").write(page)
print("Built index.html with %d picks" % len(data["products"]))
