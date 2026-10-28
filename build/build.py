"""Builds the README's SVGs (light + dark) into ../assets.

  python3 build/fonts.py   # once: subset fonts -> build/fonts.json
  python3 build/build.py

Colours are the site's tokens (Tobacco & Brass, and its dark twin Espresso Night).
The desk comes from the site, captured as build/desk-light.svg.
"""
import base64, json, random, re, subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

HERE = Path(__file__).parent
ASSETS = HERE.parent / "assets"
ASSETS.mkdir(exist_ok=True)
SVGNS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVGNS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

THEMES = {
    "light": dict(paper="#f6f2e8", paper2="#ebe4d4", ink="#261d16", ink2="#5d5044", rule="#dcd2c0",
                  brand="#5a3d2b", mark="#9c7a1e", markInk="#7a5f14", dot="#261d16"),
    "dark": dict(paper="#1e1814", paper2="#29211b", ink="#efe7da", ink2="#b8ab99", rule="#3b3129",
                 brand="#b5bd7c", mark="#d08b5b", markInk="#dc9c70", dot="#efe7da"),
}

FONTS = json.loads((HERE / "fonts.json").read_text())
FAMILY = {"sans600": ("IS", 600, "normal"), "sans400": ("IS", 400, "normal"),
          "serif": ("ISerif", 400, "italic"), "mono400": ("JBM", 400, "normal"), "mono600": ("JBM", 600, "normal")}


def font_css(keys):
    out = []
    for k in keys:
        fam, w, st = FAMILY[k]
        out.append(f"@font-face{{font-family:{fam};font-weight:{w};font-style:{st};"
                   f"src:url(data:font/woff;base64,{FONTS[k]}) format('woff')}}")
    return "".join(out)


# ---- text measuring, so lines wrap and fit without a browser ------------------------------
_metrics = {}


def _font(key):
    if key not in _metrics:
        path = {"sans600": "InstrumentSans.ttf", "sans400": "InstrumentSans.ttf",
                "serif": "InstrumentSerif-Italic.ttf", "mono400": "JetBrainsMono.ttf",
                "mono600": "JetBrainsMono.ttf"}[key]
        f = TTFont(HERE / "fonts" / path)
        axes = {"sans600": {"wght": 600, "wdth": 100}, "sans400": {"wght": 400, "wdth": 100},
                "mono400": {"wght": 400}, "mono600": {"wght": 600}}.get(key)
        if axes:
            f = instancer.instantiateVariableFont(f, axes)
        _metrics[key] = (f.getBestCmap(), f["hmtx"].metrics, f["head"].unitsPerEm)
    return _metrics[key]


def width(text, key, size, tracking=0.0):
    cmap, hmtx, upm = _font(key)
    w = sum(hmtx[cmap.get(ord(c), cmap[ord("?")])][0] for c in text)
    return w / upm * size + tracking * size * len(text)


def wrap(text, key, size, maxw):
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if width(trial, key, size) <= maxw or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + [line] if line else lines


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg_doc(w, h, body, css, label):
    return (f'<svg xmlns="{SVGNS}" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="{esc(label)}"><title>{esc(label)}</title><style>{css}'
            "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>"
            f"{body}</svg>")


# ---- the desk ------------------------------------------------------------------------------
def oklab_to_hex(L, a, b):
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    rgb = (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
           -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
           -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)

    def enc(x):
        x = max(0.0, min(1.0, x))
        x = 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
        return f"{round(x * 255):02x}"
    return "#" + "".join(enc(c) for c in rgb)


def colour(v):
    m = re.fullmatch(r"oklab\(([-\d.e]+) ([-\d.e]+) ([-\d.e]+)(?: / ([\d.]+))?\)", v.strip())
    if not m:
        return v, None
    return oklab_to_hex(*map(float, m.groups()[:3])), m.group(4)


# Where each part sits when the desk is taken apart (read from the site at full scroll).
# Index = position among the desk <svg>'s children.
EXPLODE = {2: (0, 100.4), 3: (0, 43), 6: (0, 43), 7: (0, -8.6), 8: (0, -20.1), 9: (0, -137.6),
           10: (0, -74.6), 11: (0, -103.2), 12: (0, -86), 13: (0, -68.8), 14: (0, -51.6),
           15: (0, -160.6), 16: (-26.5, -169.4), 18: (0, -63.1), 19: (0, -106.1), 20: (0, -83.2),
           21: (0, -111.8)}
# Order the parts come apart in: legs first, then the top's contents from the back.
STAGGER = {2: 0, 3: 0, 6: 0, 7: 1, 8: 1, 9: 3, 10: 2, 11: 4, 12: 3, 13: 2, 14: 1, 15: 4, 16: 4,
           18: 2, 19: 3, 20: 2, 21: 3}
CYCLE = 16  # seconds


def desk_markup():
    tree = ET.parse(HERE / "desk-light.svg")
    root = tree.getroot()
    q = lambda t: f"{{{SVGNS}}}{t}"
    for el in root.iter():
        a = el.attrib
        for k in ("fill", "stroke"):
            if k in a:
                hexv, alpha = colour(a[k])
                a[k] = hexv
                if alpha is not None:
                    a[k + "-opacity"] = alpha
        if a.get("fill-opacity") == "0":
            a["fill"] = "none"
            del a["fill-opacity"]
        if a.get("stroke") == "none":
            for k in ("stroke", "stroke-width", "stroke-linejoin", "stroke-linecap", "stroke-dasharray"):
                a.pop(k, None)
        if a.get("stroke-linejoin") == "miter":
            del a["stroke-linejoin"]
        if a.get("stroke-linecap") == "butt":
            del a["stroke-linecap"]
        for k in [k for k in a if k.startswith("data-") and k != "data-filter"]:
            del a[k]
        for k in ("aria-label", "role", "tabindex", "focusable"):
            a.pop(k, None)
        if a.get("transform") == "translate(0.00 0.00)":
            del a["transform"]
        f = a.pop("data-filter", None)
        if f and f.startswith("blur"):
            a["filter"] = "url(#dk-blur)"
        elif f and f.startswith("grayscale"):
            a["filter"] = "url(#dk-gray)"
        if el.tag == q("image"):
            jpg = HERE / "me-small.jpg"
            if not jpg.exists():
                subprocess.run(["sips", "-Z", "180", "-s", "formatOptions", "70",
                                str(HERE.parent.parent / "rohan2010.github.io/public/me.jpg"),
                                "--out", str(jpg)], check=True, capture_output=True)
            a["href"] = "data:image/jpeg;base64," + base64.b64encode(jpg.read_bytes()).decode()
            a.pop("fill", None)
    kids = list(root)
    for i, el in enumerate(kids):
        if i in EXPLODE or i in (1, 17):
            el.set("class", f"p{i}")
    defs = ET.SubElement(root, q("defs"))
    defs.append(ET.fromstring(f'<filter xmlns="{SVGNS}" id="dk-blur" x="-20%" y="-20%" width="140%" height="140%">'
                              '<feGaussianBlur stdDeviation="9"/></filter>'))
    defs.append(ET.fromstring(f'<filter xmlns="{SVGNS}" id="dk-gray"><feColorMatrix type="saturate" values="0"/>'
                              '<feComponentTransfer><feFuncR type="linear" slope="1.05" intercept="-.025"/>'
                              '<feFuncG type="linear" slope="1.05" intercept="-.025"/>'
                              '<feFuncB type="linear" slope="1.05" intercept="-.025"/></feComponentTransfer></filter>'))
    inner = "".join(ET.tostring(k, encoding="unicode") for k in root)
    inner = re.sub(r' xmlns(:\w+)?="[^"]+"', "", inner)
    inner = re.sub(r"(\d+\.\d{2})\d+", r"\1", inner)  # trim long decimals from the capture
    return inner


def desk_css():
    ease = "cubic-bezier(.65,0,.35,1)"
    css = [f"text{{font-family:JBM,ui-monospace,monospace}}"]
    for i, (dx, dy) in EXPLODE.items():
        s = 10 + STAGGER[i] * 3          # start lifting (% of the cycle)
        e = s + 22                        # fully apart
        b = 62 + (4 - STAGGER[i]) * 2     # start settling back
        f = b + 18
        css.append(f"@keyframes k{i}{{0%,{s}%{{transform:translate(0,0);animation-timing-function:{ease}}}"
                   f"{e}%,{b}%{{transform:translate({dx}px,{dy}px);animation-timing-function:{ease}}}"
                   f"{f}%,100%{{transform:translate(0,0)}}}}"
                   f".p{i}{{animation:k{i} {CYCLE}s infinite}}")
    css.append(f"@keyframes fadeout{{0%,10%{{opacity:1}}20%,74%{{opacity:0}}88%,100%{{opacity:1}}}}"
               f".p1,.p17{{animation:fadeout {CYCLE}s infinite}}"
               )
    return "".join(css)


# ---- hero ----------------------------------------------------------------------------------
def dot_grid(t, w, h, step, seed, twinkles, x0=0):
    rnd = random.Random(seed)
    pat = (f'<pattern id="grid" width="{step}" height="{step}" patternUnits="userSpaceOnUse">'
           f'<circle cx="{step/2}" cy="{step/2}" r="1.15" fill="{t["dot"]}"/></pattern>')
    sparks = []
    cols, rows = int((w - x0) // step), int(h // step)
    for n in range(twinkles):
        cx = x0 + (rnd.randrange(cols) + 0.5) * step
        cy = (rnd.randrange(rows) + 0.5) * step
        dur = rnd.uniform(3.5, 7)
        delay = -rnd.uniform(0, dur)
        sparks.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2" fill="{t["mark"]}" class="tw" '
                      f'style="animation-duration:{dur:.1f}s;animation-delay:{delay:.1f}s"/>')
    return pat, "".join(sparks)


def hero(theme):
    t = THEMES[theme]
    W, H = 1280, 620
    pat, sparks = dot_grid(t, W, H, 22, 7, 46, x0=560)
    head = [("I build AI that does", None), ("the ", "paperwork,"), ("so humans don’t have to.", None)]
    x, y0, lh, size = 72, 228, 62, 46
    lines = []
    for i, (plain, accent) in enumerate(head):
        y = y0 + i * lh
        if accent:
            pw = width(plain, "sans600", size)
            aw = width(accent, "serif", size * 1.18)
            lines.append(f'<text x="{x}" y="{y}" class="h">{esc(plain)}'
                         f'<tspan class="acc">{esc(accent)}</tspan></text>')
            uy = y + 12
            lines.append(f'<path class="ul" d="M{x + pw + 2:.0f} {uy} C {x + pw + aw*0.35:.0f} {uy + 7}, '
                         f'{x + pw + aw*0.7:.0f} {uy - 3}, {x + pw + aw - 6:.0f} {uy + 2}" pathLength="1"/>')
        else:
            lines.append(f'<text x="{x}" y="{y}" class="h">{esc(plain)}</text>')
    dim = ' filter="url(#dim)"' if theme == "dark" else ""
    body = f"""
<defs>{pat}
  <filter id="dim"><feComponentTransfer><feFuncR type="linear" slope=".86"/><feFuncG type="linear" slope=".83"/><feFuncB type="linear" slope=".78"/></feComponentTransfer></filter>
  <linearGradient id="fade" x1="0" x2="1"><stop offset=".38" stop-color="#fff" stop-opacity="0"/><stop offset=".62" stop-color="#fff" stop-opacity="1"/></linearGradient>
  <mask id="m"><rect width="{W}" height="{H}" fill="url(#fade)"/></mask>
  <clipPath id="card"><rect width="{W}" height="{H}" rx="18"/></clipPath>
</defs>
<g clip-path="url(#card)">
  <rect width="{W}" height="{H}" fill="{t['paper']}"/>
  <g mask="url(#m)"><rect width="{W}" height="{H}" fill="url(#grid)" opacity="{.16 if theme == 'light' else .13}"/>{sparks}</g>
  <text x="{x}" y="128" class="k">ROHAN PANT  ·  FULL-STACK + AI ENGINEER  ·  DELHI</text>
  {''.join(lines)}
  <text x="{x}" y="{y0 + 3*lh + 24}" class="s">AI agents in production, a NeurIPS 2024 paper,</text>
  <text x="{x}" y="{y0 + 3*lh + 54}" class="s">and an M.S. in Human-Computer Interaction from Purdue.</text>
  <text x="{x}" y="{H - 64}" class="u">rohan2010.github.io<tspan class="cur">_</tspan></text>
  <svg x="620" y="0" width="660" height="{H}" viewBox="60 -215 960 975"><g{dim}>{desk_markup()}</g></svg>
</g>
<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="18" fill="none" stroke="{t['rule']}"/>"""
    css = (font_css(["sans600", "sans400", "serif", "mono400", "mono600"]) +
           f".k{{font:600 15px JBM,monospace;letter-spacing:.12em;fill:{t['markInk']}}}"
           f".h{{font:600 {size}px IS,sans-serif;letter-spacing:-.02em;fill:{t['ink']}}}"
           f".acc{{font:400 {size*1.18:.0f}px ISerif,serif;font-style:italic;letter-spacing:0;fill:{t['markInk']}}}"
           f".s{{font:400 21px IS,sans-serif;fill:{t['ink2']}}}"
           f".u{{font:400 17px JBM,monospace;fill:{t['ink']}}}"
           f".ul{{fill:none;stroke:{t['mark']};stroke-width:3;stroke-linecap:round;stroke-dasharray:1;"
           f"stroke-dashoffset:1;animation:draw {CYCLE}s infinite}}"
           f"@keyframes draw{{0%,4%{{stroke-dashoffset:1}}14%,90%{{stroke-dashoffset:0}}97%,100%{{stroke-dashoffset:1}}}}"
           f".cur{{fill:{t['mark']};animation:blink 1.1s steps(1) infinite}}@keyframes blink{{50%{{opacity:0}}}}"
           f".tw{{opacity:0;animation:tw 5s ease-in-out infinite}}@keyframes tw{{0%,100%{{opacity:0}}50%{{opacity:.85}}}}"
           + desk_css())
    return svg_doc(W, H, body, css, "Rohan Pant, full-stack and AI engineer in Delhi: I build AI that does "
                   "the paperwork, so humans don't have to. Beside it, his isometric desk comes apart and "
                   "goes back together.")


# ---- project cards -------------------------------------------------------------------------
PROJECTS = [
    dict(slug="onboarding-agent", n="01", name="Seller onboarding agent", year="2024 – now",
         tag="days → minutes", tagNote="seller activation",
         line="A LangGraph agent that checks a new seller's KYC, tax and legal documents, and retries "
              "a failed check instead of guessing.",
         nodes={"upload": ("Seller uploads", 0, 0), "read": ("Read the document", 1, 0),
                "check": ("Validate fields", 2, 0), "route": ("Route", 3, 0),
                "retry": ("Retry", 2, -1), "live": ("Seller live", 4, 0)},
         edges=[("upload", "read"), ("read", "check"), ("check", "route"), ("route", "retry"),
                ("retry", "read"), ("route", "live")],
         run=["upload", "read", "check", "route", "retry", "read", "check", "route", "live"]),
    dict(slug="bloomscroll", n="02", name="bloomScroll", year="2026", tag="MIT", tagNote="open source",
         line="A Chrome extension that hides off-topic YouTube videos, decided on your own computer.",
         nodes={"feed": ("YouTube feed", 0, 0), "rules": ("Corrections + rules", 1, 0),
                "embed": ("MiniLM embeddings", 2, 0), "llm": ("Local model", 3, 0),
                "hide": ("Keep or dissolve", 4, 0)},
         edges=[("feed", "rules"), ("rules", "embed"), ("embed", "llm"), ("llm", "hide"), ("hide", "rules")],
         run=["feed", "rules", "embed", "llm", "hide", "rules"]),
    dict(slug="value-imprint", n="03", name="Value Imprint", year="2024", tag="NeurIPS 2024",
         tagNote="spotlight poster",
         line="A NeurIPS 2024 paper that measures which human values sit inside the data used to "
              "align language models.",
         nodes={"lit": ("Ethics literature", 0, 0), "tax": ("Values taxonomy", 1, 0),
                "ann": ("Hand labels", 2, 0), "clf": ("RoBERTa classifier", 3, 0),
                "audit": ("Label 3 datasets", 4, 0), "check": ("Human check", 5, 0)},
         edges=[("lit", "tax"), ("tax", "ann"), ("ann", "clf"), ("clf", "audit"), ("audit", "check")],
         run=["lit", "tax", "ann", "clf", "audit", "check"]),
    dict(slug="decentralmem", n="04", name="DecentralMem", year="2026", tag="MCP", tagNote="in progress",
         line="Project memory for AI assistants: write a decision once, get it back in the next chat.",
         nodes={"client": ("Claude, over MCP", 0, 0), "mcp": ("MCP server", 1, 0),
                "pg": ("PostgreSQL", 1.5, -1), "emb": ("Embedding service", 2, 0),
                "qd": ("Qdrant", 3, 0), "cwm": ("Context budget", 4, 0)},
         edges=[("client", "mcp"), ("mcp", "pg"), ("mcp", "emb"), ("emb", "qd"), ("qd", "cwm"),
                ("cwm", "client")],
         run=["client", "mcp", "emb", "qd", "cwm", "client"]),
]


def card(p, theme):
    t = THEMES[theme]
    W, H, pad = 640, 360, 36
    cols = max(c for _, c, _ in p["nodes"].values())
    gx0, gx1, gy = pad + 34, W - pad - 34, 268
    rowh = 44
    pos = {k: (gx0 + (gx1 - gx0) * c / cols, gy + r * rowh) for k, (_, c, r) in p["nodes"].items()}

    def seg(a, b):
        (x1, y1), (x2, y2) = pos[a], pos[b]
        if x2 < x1 and y1 == y2:  # a loop back along the row: arc over the top
            lift = 30 + (x1 - x2) * 0.08
            return f"C {x1} {y1 - lift*1.6}, {x2} {y2 - lift*1.6}, {x2} {y2}"
        return f"L {x2:.1f} {y2:.1f}"

    edges = "".join(f'<path d="M {pos[a][0]:.1f} {pos[a][1]:.1f} {seg(a, b)}" class="e"/>' for a, b in p["edges"])
    nodes, labels = [], []
    for k, (label, c, r) in p["nodes"].items():
        x, y = pos[k]
        nodes.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" class="n"/>')
        ls = wrap(label, "sans400", 13, 96)
        if r < 0:
            labels.append(f'<text x="{x + 12:.1f}" y="{y + 4:.1f}" class="nl">{esc(" ".join(ls))}</text>')
        else:
            labels.append("".join(f'<text x="{x:.1f}" y="{y + 26 + j*16:.1f}" class="nl" text-anchor="middle">'
                                  f"{esc(s)}</text>" for j, s in enumerate(ls)))
    run = p["run"]
    route = f"M {pos[run[0]][0]:.1f} {pos[run[0]][1]:.1f} " + " ".join(seg(a, b) for a, b in zip(run, run[1:]))
    dur = 1.15 * (len(run) - 1)
    pulse = (f'<circle r="5.5" class="pulse"><animateMotion dur="{dur:.1f}s" repeatCount="indefinite" '
             f'path="{route}" calcMode="paced"/></circle>'
             f'<circle r="11" class="halo"><animateMotion dur="{dur:.1f}s" repeatCount="indefinite" '
             f'path="{route}" calcMode="paced"/></circle>')
    lines = wrap(p["line"], "sans400", 18, W - 2 * pad - 10)
    desc = "".join(f'<text x="{pad}" y="{150 + i*26}" class="d">{esc(s)}</text>' for i, s in enumerate(lines))
    tagw = width(p["tag"], "mono600", 14, .04) + 24
    body = f"""
<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="16" fill="{t['paper']}" stroke="{t['rule']}"/>
<text x="{pad}" y="{pad + 22}" class="k">{p['n']}  ·  {esc(p['year'].upper())}</text>
<g transform="translate({W - pad - tagw:.1f} {pad + 4})">
  <rect width="{tagw:.1f}" height="28" rx="14" fill="none" stroke="{t['mark']}"/>
  <text x="{tagw/2:.1f}" y="19" text-anchor="middle" class="tg">{esc(p['tag'])}</text>
  <text x="{tagw - 4:.1f}" y="48" text-anchor="end" class="tn">{esc(p['tagNote'])}</text>
</g>
<text x="{pad}" y="{pad + 68}" class="nm">{esc(p['name'])}</text>
{desc}
{edges}{''.join(nodes)}{pulse}{''.join(labels)}"""
    css = (font_css(["sans600", "sans400", "mono400", "mono600"]) +
           f".k{{font:600 13px JBM,monospace;letter-spacing:.1em;fill:{t['markInk']}}}"
           f".nm{{font:600 34px IS,sans-serif;letter-spacing:-.02em;fill:{t['ink']}}}"
           f".d{{font:400 18px IS,sans-serif;fill:{t['ink2']}}}"
           f".tg{{font:600 14px JBM,monospace;letter-spacing:.04em;fill:{t['markInk']}}}"
           f".tn{{font:400 12px JBM,monospace;fill:{t['ink2']}}}"
           f".e{{fill:none;stroke:{t['ink2']};stroke-opacity:.45;stroke-width:1.5}}"
           f".n{{fill:{t['paper']};stroke:{t['ink']};stroke-width:1.5}}"
           f".nl{{font:400 13px IS,sans-serif;fill:{t['ink2']}}}"
           f".pulse{{fill:{t['mark']}}}.halo{{fill:{t['mark']};opacity:.22}}")
    return svg_doc(W, H, body, css, f"{p['name']}: {p['line']}")


# ---- a thin divider with a brass dot running along it ------------------------------------
def divider(theme):
    t = THEMES[theme]
    W, H = 1280, 24
    body = (f'<line x1="0" y1="12" x2="{W}" y2="12" stroke="{t["rule"]}" stroke-width="1.5" stroke-dasharray="2 6"/>'
            f'<circle cy="12" r="4" fill="{t["mark"]}"><animate attributeName="cx" values="-10;{W+10}" '
            f'dur="9s" repeatCount="indefinite"/></circle>')
    return svg_doc(W, H, body, "", "")


if __name__ == "__main__":
    for theme in THEMES:
        (ASSETS / f"hero-{theme}.svg").write_text(hero(theme))
        for p in PROJECTS:
            (ASSETS / f"work-{p['slug']}-{theme}.svg").write_text(card(p, theme))
        (ASSETS / f"divider-{theme}.svg").write_text(divider(theme))
    for f in sorted(ASSETS.glob("*.svg")):
        print(f"{f.name:40} {f.stat().st_size/1024:7.1f} KB")
