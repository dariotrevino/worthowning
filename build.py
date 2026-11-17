"""Builds the whole site from products.json and the templates in src/.

Run:  python3 build.py
Edit products.json to add, remove or change picks, then run this again.

Writes:
  index.html                 home page with the grid
  picks/<slug>/index.html    one page per pick
  sitemap.xml, robots.txt

Each pick's "why" is a list of paragraphs in your own words. A pick with no
"why" yet still gets a page, but it is marked noindex and left out of the
sitemap until you write it, so Google never sees a page with no text on it.
"""
import datetime, html, json, os, re, shutil

SITE = "https://worthowning.net/"

data = json.load(open("products.json", encoding="utf-8"))
CSS = open("src/style.css", encoding="utf-8").read()
HOME = open("src/page.html", encoding="utf-8").read()
PRODUCT = open("src/product.html", encoding="utf-8").read()
TAG = data.get("amazon_tag", "")
CHECKED = data.get("prices_checked", "")
cats = {c["id"]: c["label"] for c in data["categories"]}
tags = {t["id"]: t["label"] for t in data["tags"]}
e = html.escape


# ---------- helpers ----------

def is_amazon(url):
    return re.match(r"^https://(www\.)?amazon\.com/", url or "") is not None

def store_link(p):
    """Returns (url, rel) for the outbound store link."""
    url = p.get("url") or ""
    paid = bool(p.get("affiliate"))
    if TAG and is_amazon(url):
        url += ("&" if "?" in url else "?") + "tag=" + TAG
        paid = True
    return url, ("sponsored nofollow noopener" if paid else "noopener"), paid

def money(p):
    v = p["price"]
    s = "${:,.0f}".format(v) if float(v).is_integer() else "${:,.2f}".format(v)
    return ("from " if p.get("from") else "") + s

def name_html(text):
    # Keeps model numbers such as G-1205 from splitting across lines.
    out = []
    for w in text.split(" "):
        out.append('<span class="nb">%s</span>' % e(w) if "-" in w else e(w))
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

def img_tag(p, lazy=False, priority=False):
    w, h = image_size(p["image"])
    return '<img src="/%s" alt="%s"%s%s%s decoding="async">' % (
        e(p["image"]), e(p["brand"] + " " + p["name"]),
        ' width="%d" height="%d"' % (w, h) if w else "",
        ' loading="lazy"' if lazy else "",
        ' fetchpriority="high"' if priority else "")

def art(p, extra="", lazy=False, priority=False):
    if p.get("image"):
        return '<div class="art photo%s" aria-hidden="true">%s</div>' % (extra, img_tag(p, lazy, priority))
    return '<div class="art%s" aria-hidden="true"><span class="tile-mono">%s</span></div>' % (extra, e(p["brand"][0]))

def page_url(p):
    return "/picks/%s/" % p["slug"]

def has_copy(p):
    return any((s or "").strip() for s in p.get("why", []))

def json_ld(obj):
    return '<script type="application/ld+json">%s</script>' % (
        json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))

def analytics():
    ga = data.get("ga_id", "")
    if not ga:
        return ""
    return ('<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>\n'
            '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}'
            'gtag("js",new Date());gtag("config","%s");</script>\n') % (ga, ga)

def card(p, lazy):
    meta = e(p["brand"]) + (" · " + e(cats[p["cat"]]) if p.get("cat") else "")
    price = '<p class="price">%s</p>' % money(p) if p.get("price") is not None else ""
    return ('<a class="card" href="%s">%s<div class="info"><p class="meta">%s</p>'
            '<div class="row"><h3 class="name">%s</h3>%s</div></div></a>') % (
        page_url(p), art(p, lazy=lazy), meta, name_html(p["name"]), price)


# ---------- checks ----------

products = data["products"]
seen = set()
for p in products:
    if not p.get("slug"):
        raise SystemExit("Missing slug for %s %s" % (p["brand"], p["name"]))
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", p["slug"]):
        raise SystemExit("Bad slug %r: use lowercase letters, numbers and hyphens" % p["slug"])
    if p["slug"] in seen:
        raise SystemExit("Duplicate slug %r" % p["slug"])
    seen.add(p["slug"])
live = [p for p in products if not p.get("pending")]


# ---------- home page ----------

def tab(fid, label, on=False):
    return '<button class="tab" type="button" data-filter="%s" aria-pressed="%s">%s</button>' % (
        fid, "true" if on else "false", e(label))

tabs = [tab("all", "All", True), tab("yours", "Your picks")]
tabs += [tab(t["id"], t["label"]) for t in data["tags"]]
tabs.append('<span class="sep" aria-hidden="true"></span>')
tabs += [tab(c["id"], c["label"]) for c in data["categories"]]

items = []
for i, p in enumerate(live):
    items.append('<li data-cat="%s" data-tags="%s" data-price="%s"%s>%s</li>' % (
        e(p.get("cat") or ""), e(" ".join(p.get("tags", []))),
        "" if p.get("price") is None else p["price"],
        " data-yours" if p.get("yours") else "", card(p, lazy=i >= 6)))

home_schema = {
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
             {"@type": "ListItem", "position": i + 1, "name": p["brand"] + " " + p["name"],
              "url": SITE.rstrip("/") + page_url(p)}
             for i, p in enumerate(live)]}},
    ],
}

home = HOME
for k, v in {
    "{{CSS}}": CSS,
    "{{TABS}}": "".join(tabs),
    "{{GRID}}": "\n      " + "\n      ".join(items) + "\n    ",
    "{{AMAZON_HIDDEN}}": "" if TAG else " hidden",
    "{{PRICES_CHECKED}}": e(CHECKED),
    "{{SCHEMA}}": json_ld(home_schema),
    "{{ANALYTICS}}": analytics(),
}.items():
    home = home.replace(k, v)
open("index.html", "w", encoding="utf-8").write(home)


# ---------- product pages ----------

def related(p, n=4):
    same = [q for q in live if q is not p and q.get("cat") == p.get("cat")]
    rest = [q for q in live if q is not p and q not in same]
    return (same + rest)[:n]

def describe(p):
    if has_copy(p):
        text = " ".join(s.strip() for s in p["why"] if s.strip())
        if len(text) > 158:
            text = text[:155].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
        return text
    return "%s %s, one of the picks on Worth Owning: a short list of buy it for life gear." % (
        p["brand"], p["name"])

if os.path.isdir("picks"):
    shutil.rmtree("picks")  # rebuilt from scratch so removed picks disappear

for p in live:
    url, rel, paid = store_link(p)
    full_url = SITE.rstrip("/") + page_url(p)
    cat = p.get("cat")

    crumbs = '<a href="/">Worth Owning</a> / '
    if cat:
        crumbs += '<a href="/#%s">%s</a> / ' % (e(cat), e(cats[cat]))
    crumbs += '<span aria-current="page">%s</span>' % e(p["name"])

    chips = "".join('<a href="/#%s">%s</a>' % (e(t), e(tags[t])) for t in p.get("tags", []) if t in tags)
    chips = '<p class="chips">%s</p>' % chips if chips else ""

    why = "".join("<p>%s</p>" % e(s.strip()) for s in p.get("why", []) if (s or "").strip())
    why = '<div class="why">%s</div>' % why if why else ""

    buy = ""
    if url:
        price = ""
        if p.get("price") is not None:
            price = '<p class="price">%s<span class="when">when checked in %s</span></p>' % (
                money(p), e(CHECKED))
        buy = ('<div class="buy"><a class="btn" href="%s" rel="%s">View at %s'
               '<svg viewBox="0 0 10 10" width="10" height="10" aria-hidden="true"><path d="M2 8 8 2M3.2 2H8v4.8" '
               'fill="none" stroke="currentColor" stroke-width="1.2"/></svg></a>%s</div>') % (
            e(url), rel, e(p["store"]), price)
        note = []
        if paid:
            note.append("I may earn a commission if you buy through this link, at no extra cost to you.")
        if TAG and is_amazon(p.get("url")):
            note.append("As an Amazon Associate I earn from qualifying purchases.")
        if note:
            buy += '<p class="fineprint">%s <a href="/#disclosure">Details</a></p>' % " ".join(note)

    more = related(p)
    more_html = ""
    if more:
        heading = "More in %s" % cats[cat] if cat and all(q.get("cat") == cat for q in more[:3]) else "More worth owning"
        more_html = ('<section class="more" aria-labelledby="more-h"><h2 id="more-h">%s</h2>'
                     '<ul class="grid">%s</ul></section>') % (
            e(heading), "".join("<li>%s</li>" % card(q, lazy=True) for q in more))

    crumb_items = [{"@type": "ListItem", "position": 1, "name": "Worth Owning", "item": SITE}]
    if cat:
        crumb_items.append({"@type": "ListItem", "position": 2, "name": cats[cat], "item": SITE + "#" + cat})
    crumb_items.append({"@type": "ListItem", "position": len(crumb_items) + 1, "name": p["name"], "item": full_url})
    schema = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "@id": full_url, "url": full_url, "name": p["brand"] + " " + p["name"],
         "description": describe(p), "isPartOf": {"@id": SITE + "#website"},
         "primaryImageOfPage": SITE + p["image"] if p.get("image") else None},
        {"@type": "BreadcrumbList", "itemListElement": crumb_items},
    ]}
    if not p.get("image"):
        del schema["@graph"][0]["primaryImageOfPage"]

    out = PRODUCT
    for k, v in {
        "{{TITLE}}": e("%s %s · Worth Owning" % (p["brand"], p["name"])),
        "{{OG_TITLE}}": e("%s %s" % (p["brand"], p["name"])),
        "{{DESCRIPTION}}": e(describe(p)),
        "{{URL}}": full_url,
        "{{ROBOTS}}": "index, follow, max-image-preview:large" if has_copy(p) else "noindex, follow",
        "{{OG_IMAGE}}": SITE + p["image"] if p.get("image") else SITE + "og-image.png",
        "{{SCHEMA}}": json_ld(schema),
        "{{ANALYTICS}}": analytics(),
        "{{CSS}}": CSS,
        "{{CRUMBS}}": crumbs,
        "{{ART}}": art(p, extra=" pick-art", priority=True),
        "{{BRAND}}": e(p["brand"]),
        "{{NAME}}": name_html(p["name"]),
        "{{CHIPS}}": chips,
        "{{WHY}}": why,
        "{{BUY}}": buy,
        "{{MORE}}": more_html,
    }.items():
        out = out.replace(k, v)
    os.makedirs("picks/" + p["slug"], exist_ok=True)
    open("picks/%s/index.html" % p["slug"], "w", encoding="utf-8").write(out)


# ---------- sitemap and robots ----------

today = datetime.date.today().isoformat()
urls = [SITE] + [SITE.rstrip("/") + page_url(p) for p in live if has_copy(p)]
open("sitemap.xml", "w", encoding="utf-8").write(
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + "".join("  <url><loc>%s</loc><lastmod>%s</lastmod></url>\n" % (u, today) for u in urls)
    + "</urlset>\n")
open("robots.txt", "w", encoding="utf-8").write(
    "User-agent: *\nAllow: /\n\nSitemap: %ssitemap.xml\n" % SITE)

written = sum(1 for p in live if has_copy(p))
print("Built index.html and %d pick pages (%d with copy, %d waiting on copy and set to noindex)"
      % (len(live), written, len(live) - written))
