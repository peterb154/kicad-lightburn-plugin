"""Combine per-purpose SVGs into one file with LightBurn-separable colours.

LightBurn assigns imported geometry to layers by matching stroke colour to its
palette, so each purpose gets its own clearly distinct colour. Filled artwork
carries the colour on BOTH fill and stroke: the fill is what actually burns,
the stroke is what LightBurn reads for layer assignment.
"""
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

DRAWABLE = ("path", "rect", "circle", "ellipse", "line", "polyline", "polygon")

# purpose -> (colour, filled)
STYLES = {
    "copper": ("#000000", True),
    "drills": ("#FF0000", False),
    "cuts":   ("#0000FF", False),
    "fiducials": ("#00E000", False),
}


def _style(colour, filled):
    if filled:
        return ("fill:%s;fill-opacity:1;fill-rule:evenodd;"
                "stroke:%s;stroke-width:0.01" % (colour, colour))
    return "fill:none;stroke:%s;stroke-width:0.1" % colour


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
        colour, filled = STYLES.get(purpose, ("#000000", False))
        grp = ET.SubElement(root, "{%s}g" % SVG_NS,
                            {"id": "klb_" + purpose, "style": _style(colour, filled)})
        n = 0
        src = ET.parse(path).getroot()
        for tag in DRAWABLE:
            for el in src.iter("{%s}%s" % (SVG_NS, tag)):
                el.attrib.pop("style", None)   # inherit the group's colour
                el.attrib.pop("fill", None)
                el.attrib.pop("stroke", None)
                grp.append(el)
                n += 1
        counts[purpose] = n
    ET.ElementTree(root).write(dst, xml_declaration=True, encoding="utf-8")
    return dst, counts
