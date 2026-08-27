"""Combine per-purpose SVGs into one file with LightBurn-separable colours.

LightBurn assigns imported geometry to layers by matching stroke colour to its
palette, so each purpose gets its own clearly distinct colour. Filled artwork
carries the colour on BOTH fill and stroke: the fill is what actually burns,
the stroke is what LightBurn reads for layer assignment.
"""
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
INK_NS = "http://www.inkscape.org/namespaces/inkscape"
ET.register_namespace("", SVG_NS)
ET.register_namespace("inkscape", INK_NS)

DRAWABLE = ("path", "rect", "circle", "ellipse", "line", "polyline", "polygon")

# purpose -> (colour, filled, LightBurn layer, human label)
#
# SVG itself has no layer concept, and LightBurn maps geometry to layers by
# COLOUR only -- it ignores id, <title> and Inkscape's layer labels. So the
# colours below are exact LightBurn palette entries, which is what makes the
# layer assignment deterministic rather than whatever slot happens to be next.
# The names are carried anyway so the file is legible in Inkscape and to a
# human reading the XML.
STYLES = {
    "copper":    ("#000000", True,  "C00", "Copper isolation"),
    "cuts":      ("#0000FF", False, "C01", "Edge cuts"),
    "drills":    ("#FF0000", False, "C02", "Drills"),
    "fiducials": ("#00E000", False, "C03", "Registration holes"),
    "mask":      ("#FF00FF", True,  "C07", "Solder mask openings"),
}


def layer_map(purposes):
    """[(purpose, 'C00', 'Copper isolation')] for the purposes given."""
    out = []
    for p in purposes:
        if p in STYLES:
            out.append((p, STYLES[p][2], STYLES[p][3]))
    return out


def _style(colour, filled):
    if filled:
        return ("fill:%s;fill-opacity:1;fill-rule:evenodd;"
                "stroke:%s;stroke-width:0.01" % (colour, colour))
    return "fill:none;stroke:%s;stroke-width:0.1" % colour


SKIP = ("defs", "namedview", "metadata", "title", "desc")


def _strip_paint(el):
    """Drop per-element paint so the layer group's colour is inherited.

    Transforms are left alone: an ancestor <g transform=...> is what carries
    the back-side X=0 mirror, and flattening elements out of it silently
    un-mirrors the artwork.
    """
    el.attrib.pop("style", None)
    el.attrib.pop("fill", None)
    el.attrib.pop("stroke", None)
    for kid in el:
        _strip_paint(kid)


def _count(el):
    n = 1 if el.tag.split("}")[-1] in DRAWABLE else 0
    return n + sum(_count(k) for k in el)


def combine(sources, dst):
    """sources: [(purpose, svg_path)] -> one multi-colour SVG.

    All sources must share a canvas; that holds because every layer is plotted
    from the same board with the same aux origin, and the drill SVG copies its
    header from a plotted layer.
    """
    if not sources:
        raise ValueError("no sources to combine")
    first = ET.parse(sources[0][1]).getroot()
    root = ET.Element("{%s}svg" % SVG_NS, {
        "version": "1.1",
        "width": first.get("width", ""), "height": first.get("height", ""),
        "viewBox": first.get("viewBox", ""),
    })
    counts = {}
    for purpose, path in sources:
        colour, filled, lb_layer, label = STYLES.get(
            purpose, ("#000000", False, "C00", purpose))
        grp = ET.SubElement(root, "{%s}g" % SVG_NS, {
            "id": "klb_" + purpose,
            "style": _style(colour, filled),
            "{%s}groupmode" % INK_NS: "layer",
            "{%s}label" % INK_NS: "%s (%s)" % (label, lb_layer),
        })
        title = ET.SubElement(grp, "{%s}title" % SVG_NS)
        title.text = "%s -- LightBurn %s" % (label, lb_layer)
        n = 0
        for el in list(ET.parse(path).getroot()):
            if not el.tag.startswith("{%s}" % SVG_NS):
                continue
            if el.tag.split("}")[-1] in SKIP:
                continue
            _strip_paint(el)
            grp.append(el)          # keeps the subtree, and its transforms
            n += _count(el)
        counts[purpose] = n
    ET.ElementTree(root).write(dst, xml_declaration=True, encoding="utf-8")
    return dst, counts


def set_canvas(svg_path, box_mm):
    """Retarget an SVG's page onto box_mm without moving any geometry.

    KiCad plots onto its page (A4 by default), which leaves the artwork at
    negative coordinates far from the page origin. LightBurn centres imports
    on the workspace by default, and a Shift-import -- which preserves file
    coordinates -- would then drop the artwork off-page. Giving every emitted
    file the SAME page, tight around the artwork, makes both routes land
    consistently. Only the viewBox moves; path data is untouched, so the
    shared drill/place origin is preserved.
    """
    x, y, w, h = box_mm
    tree = ET.parse(svg_path)
    root = tree.getroot()
    root.set("width", "%.6fmm" % w)
    root.set("height", "%.6fmm" % h)
    root.set("viewBox", "%.6f %.6f %.6f %.6f" % (x, y, w, h))
    tree.write(svg_path, xml_declaration=True, encoding="utf-8")
    return box_mm
