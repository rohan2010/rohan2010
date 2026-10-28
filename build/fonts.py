"""Subset the site's fonts (OFL) to Latin and save them as base64 WOFF for embedding in SVGs."""
import base64, io, json
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools import subset

TEXT = "".join(chr(c) for c in range(0x20, 0x7F)) + "·→←↗✓✗—–’‘“”•×é…↺"
FACES = {
    "sans600": ("fonts/InstrumentSans.ttf", {"wght": 600, "wdth": 100}),
    "sans400": ("fonts/InstrumentSans.ttf", {"wght": 400, "wdth": 100}),
    "serif": ("fonts/InstrumentSerif-Italic.ttf", None),
    "mono400": ("fonts/JetBrainsMono.ttf", {"wght": 400}),
    "mono600": ("fonts/JetBrainsMono.ttf", {"wght": 600}),
}
out = {}
for key, (path, axes) in FACES.items():
    font = TTFont(path)
    if axes:
        font = instancer.instantiateVariableFont(font, axes)
    opts = subset.Options()
    opts.flavor = "woff"
    opts.layout_features = ["kern", "liga"]
    opts.name_IDs = []
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    sub.populate(text=TEXT)
    sub.subset(font)
    font.flavor = "woff"
    buf = io.BytesIO()
    font.save(buf)
    out[key] = base64.b64encode(buf.getvalue()).decode()
    print(key, len(buf.getvalue()))
json.dump(out, open("fonts.json", "w"))
