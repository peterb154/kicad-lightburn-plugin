"""Drill artwork: vias and through-hole pads as circles.

Coordinates are emitted relative to the aux (drill/place) origin, and the SVG
header is copied verbatim from a plotted copper SVG, so the drill layer lands
in exactly the same coordinate space as the copper artwork.
"""
import xml.etree.ElementTree as ET

import pcbnew

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def collect(board):
    """[(x_mm, y_mm, dia_mm)] relative to aux origin, for vias + TH pads."""
    ds = board.GetDesignSettings()
    o = getattr(ds, "GetAuxOrigin", None)
    o = o() if callable(o) else getattr(ds, "m_AuxOrigin", None)
    ax, ay = (pcbnew.ToMM(o.x), pcbnew.ToMM(o.y)) if o is not None else (0.0, 0.0)

    holes = []
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            p = t.GetPosition()
            holes.append((pcbnew.ToMM(p.x) - ax, pcbnew.ToMM(p.y) - ay,
                          pcbnew.ToMM(t.GetDrillValue())))
    th = (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() not in th:
                continue
            d = pad.GetDrillSize()
            dia = min(pcbnew.ToMM(d.x), pcbnew.ToMM(d.y))
            if dia <= 0:
                continue
            p = pad.GetPosition()
            holes.append((pcbnew.ToMM(p.x) - ax, pcbnew.ToMM(p.y) - ay, dia))
    return holes


def partition(board, frame_mm):
    """Split holes into (in_board, registration).

    Holes outside the board outline are dowel/registration features, not part
    fixings -- they get their own layer so they can be cut first and used to
    pin the blank for the two-sided flip.
    """
    x0, y0, w, h = frame_mm
    x1, y1 = x0 + w, y0 + h
    inside, reg = [], []
    for hole in collect(board):
        x, y, _ = hole
        (inside if (x0 <= x <= x1 and y0 <= y <= y1) else reg).append(hole)
    return inside, reg


def write_svg(board, ref_svg, dst, mirror_about_x0=False, holes=None):
    """Write a drill SVG sharing ref_svg's canvas. Returns (path, count)."""
    ref = ET.parse(ref_svg).getroot()
    root = ET.Element("{%s}svg" % SVG_NS, {
        "version": "1.1",
        "width": ref.get("width", ""), "height": ref.get("height", ""),
        "viewBox": ref.get("viewBox", ""),
    })
    if holes is None:
        holes = collect(board)
    for x, y, dia in holes:
        if mirror_about_x0:
            x = -x
        ET.SubElement(root, "{%s}circle" % SVG_NS, {
            "cx": "%.6f" % x, "cy": "%.6f" % y, "r": "%.6f" % (dia / 2.0),
            "style": "fill:none;stroke:#000000;stroke-width:0.05",
        })
    ET.ElementTree(root).write(dst, xml_declaration=True, encoding="utf-8")
    return dst, len(holes)
