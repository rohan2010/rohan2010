"""Writes the desk as an ASCII STL (GitHub renders it as a 3D model you can rotate)
and the map as GeoJSON, then drops both into README.md between their markers."""
import json, re
from pathlib import Path

ROOT = Path(__file__).parent.parent

# The desk, in boxes: (x, y, z, width, depth, height). Units are centimetres-ish.
BOXES = [
    (0, 0, 70, 140, 70, 4),          # top
    (4, 4, 0, 5, 5, 70), (131, 4, 0, 5, 5, 70), (4, 61, 0, 5, 5, 70), (131, 61, 0, 5, 5, 70),  # legs
    (6, 6, 62, 128, 3, 8), (6, 61, 62, 128, 3, 8),                                             # apron
    (30, 8, 74, 80, 30, 0.6),        # desk mat
    (40, 14, 74.6, 44, 14, 2.4),     # keyboard
    (88, 16, 74.6, 9, 6, 1.6),       # controller
    (58, 50, 74, 22, 12, 1.2),       # monitor foot
    (67, 54, 75.2, 4, 3, 16),        # monitor neck
    (44, 52, 88, 50, 2.5, 30),       # monitor screen
    (104, 46, 74, 1.5, 9, 13),       # photo frame
    (10, 48, 74, 13, 13, 12),        # plant pot
    (14, 52, 86, 1.6, 1.6, 18), (17, 54, 86, 1.6, 1.6, 22), (19, 51, 86, 1.6, 1.6, 15),  # leaves
    (12, 20, 74, 20, 26, 3),         # project folders
    (112, 12, 74, 16, 22, 1.2),      # clipboard
]


def box_facets(x, y, z, w, d, h):
    v = [(x + dx * w, y + dy * d, z + dz * h) for dz in (0, 1) for dy in (0, 1) for dx in (0, 1)]
    quads = [((0, 2, 3, 1), (0, 0, -1)), ((4, 5, 7, 6), (0, 0, 1)), ((0, 1, 5, 4), (0, -1, 0)),
             ((2, 6, 7, 3), (0, 1, 0)), ((0, 4, 6, 2), (-1, 0, 0)), ((1, 3, 7, 5), (1, 0, 0))]
    for (a, b, c, e), n in quads:
        for tri in ((a, b, c), (a, c, e)):
            yield n, [v[i] for i in tri]


def stl():
    fmt = lambda p: " ".join(f"{c:g}" for c in p)
    out = ["solid desk"]
    for b in BOXES:
        for n, tri in box_facets(*b):
            out.append(f"facet normal {fmt(n)}\nouter loop")
            out += [f"vertex {fmt(p)}" for p in tri]
            out.append("endloop\nendfacet")
    out.append("endsolid desk")
    return "\n".join(out)


def place(name, lon, lat, what, kind):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"name": name, "what": what,
                           "marker-color": "#9c7a1e" if kind == "lived" else "#5a3d2b",
                           "marker-symbol": "star" if kind == "lived" else "circle", "marker-size": "medium"}}


def geojson():
    delhi, purdue = [77.209, 28.6139], [-86.9212, 40.4237]
    feats = [
        place("Delhi", delhi[0], delhi[1], "Home. B.Tech in IT (2018 – 2022); based here now.", "lived"),
        place("West Lafayette, Indiana", purdue[0], purdue[1], "M.S. in Human-Computer Interaction, Purdue (2022 – 2024).", "lived"),
        place("Chicago", -87.6244, 41.8827, "The photo on the desk: Lake Michigan.", "visit"),
        place("Dubai", 55.2708, 25.2048, "Let's Dunch, a remote software engineering job (2021 – 2022).", "remote"),
        place("New York", -74.006, 40.7128, "My day job, remote (2024 – now).", "remote"),
        place("Vancouver", -123.1207, 49.2827, "Where NeurIPS 2024 was held; Value Imprint was a spotlight poster.", "remote"),
        {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [delhi, purdue]},
         "properties": {"name": "Delhi → Purdue → Delhi", "stroke": "#9c7a1e", "stroke-width": 2}},
    ]
    return json.dumps({"type": "FeatureCollection", "features": feats}, indent=1)


def inject(text, marker, body, lang):
    pat = re.compile(rf"(<!-- {marker}:START -->).*?(<!-- {marker}:END -->)", re.S)
    return pat.sub(lambda m: f"{m.group(1)}\n```{lang}\n{body}\n```\n{m.group(2)}", text)


if __name__ == "__main__":
    readme = ROOT / "README.md"
    text = readme.read_text()
    text = inject(text, "DESK-STL", stl(), "stl")
    text = inject(text, "MAP", geojson(), "geojson")
    readme.write_text(text)
    print("README.md updated:", len(text.splitlines()), "lines")
