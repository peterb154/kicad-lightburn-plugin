"""KiCad copper SVG -> LightBurn isolation artwork.

Stages, matching the verified manual pipeline:
  1. union      stroked traces + pads -> one fillable outline
  2. dilate     grow copper by the moat offset (optional)
  3. frame      inject a board-sized rect as the FIRST child (bottom of z-order)
  4. difference frame minus copper -> the isolation regions

Stage 2 replaces Inkscape's path-outset, which does not exist as an action in
Inkscape 1.2+ (it was a verb, and verbs were removed). We instead stroke the
unioned copper by 2*offset and re-run stroke-to-path + union, which dilates the
outline by exactly `offset` on every side. Measured accurate to <1um.
"""
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET

try:
    from . import inkscape
except ImportError:  # standalone / test use
    import inkscape

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

UNION_ACTIONS = ("select-all:all;object-to-path;object-stroke-to-path;"
                 "selection-ungroup;path-union")
DIFF_ACTIONS = "select-all:all;object-to-path;path-difference"


class TransformError(RuntimeError):
    pass


def _export(actions, out_name):
    return "{};export-filename:{};export-do".format(actions, out_name)


def _paths(svg_file):
    root = ET.parse(svg_file).getroot()
    return root, root.findall(".//{%s}path" % SVG_NS)


def union(work, src, dst):
    inkscape.run_actions(work, src, _export(UNION_ACTIONS, dst))
    _, paths = _paths(os.path.join(work, dst))
    if not paths:
        raise TransformError(
            "Union produced no geometry from {}. The layer is empty, or the "
            "plot contained nothing fillable.".format(src))
    return dst


def dilate(work, src, dst, offset_mm):
    """Grow copper outward by offset_mm via stroke expansion."""
    if offset_mm <= 0:
        shutil.copyfile(os.path.join(work, src), os.path.join(work, dst))
        return dst
    stroked = "_dil_in.svg"
    tree = ET.parse(os.path.join(work, src))
    grew = 0
    for el in tree.getroot().iter("{%s}path" % SVG_NS):
        style = el.get("style", "")
        el.set("style", style.rstrip("; ") +
               ";fill:#000000;stroke:#000000;stroke-width:{:g};"
               "stroke-linejoin:round;stroke-linecap:round".format(offset_mm * 2.0))
        grew += 1
    if not grew:
        raise TransformError("No paths to dilate in " + src)
    tree.write(os.path.join(work, stroked))
    inkscape.run_actions(work, stroked, _export(UNION_ACTIONS, dst))
    return dst


def add_frame(work, src, dst, rect_mm):
    """Insert a rect as the first child so it sits at the bottom of z-order."""
    x, y, w, h = rect_mm
    if w <= 0 or h <= 0:
        raise TransformError("Frame rect has non-positive size: %r" % (rect_mm,))
    tree = ET.parse(os.path.join(work, src))
    root = tree.getroot()
    rect = ET.Element("{%s}rect" % SVG_NS, {
        "id": "klb_frame",
        "x": "%.6f" % x, "y": "%.6f" % y,
        "width": "%.6f" % w, "height": "%.6f" % h,
        "style": "fill:#000000;fill-opacity:1;stroke:none",
    })
    root.insert(0, rect)
    tree.write(os.path.join(work, dst))
    return dst


def difference(work, src, dst):
    inkscape.run_actions(work, src, _export(DIFF_ACTIONS, dst))
    return dst


DRAWABLE = ("path", "rect", "circle", "ellipse", "line", "polyline", "polygon")


def _counts(work, name):
    """(drawable elements, <path> elements, total subpaths)."""
    root = ET.parse(os.path.join(work, name)).getroot()
    draw = paths = subs = 0
    for tag in DRAWABLE:
        for el in root.iter("{%s}%s" % (SVG_NS, tag)):
            draw += 1
            if tag == "path":
                paths += 1
                d = el.get("d", "")
                subs += d.count("M") + d.count("m")
    return draw, paths, subs


def _validate(work, name, frame_rect, copper_subs):
    """Fail loudly if the boolean silently did nothing.

    A failed difference leaves the frame rect AND the copper in the file. The
    combined bbox still equals the frame, so bbox alone cannot detect it --
    and counting only <path> elements cannot either, because the frame is a
    <rect>. The decisive signal is that a real difference collapses every
    drawable into exactly ONE <path> carrying the copper islands as subpaths.
    """
    draw, paths, subs = _counts(work, name)
    if draw != 1 or paths != 1:
        raise TransformError(
            "Difference did not merge: {} drawable element(s), {} path(s); "
            "expected exactly 1 path. The boolean failed and this artwork "
            "would be WRONG POLARITY.".format(draw, paths))
    if subs < 2:
        raise TransformError(
            "Difference produced {} subpath(s); copper islands are missing. "
            "This artwork would ablate the whole board.".format(subs))
    if subs < copper_subs:
        raise TransformError(
            "Output has {} subpaths but copper had {}; islands were dropped."
            .format(subs, copper_subs))
    bb = inkscape.drawing_bbox_mm(work, name)
    if bb is None:
        raise TransformError("Could not measure output bbox.")
    for got, want, axis in zip(bb, frame_rect, "xywh"):
        if abs(got - want) > 0.05:
            raise TransformError(
                "Output {} is {:.3f}mm, expected frame {:.3f}mm -- the "
                "difference did not use the frame.".format(axis, got, want))
    return {"paths": paths, "subpaths": subs, "copper_subpaths": copper_subs,
            "bbox_mm": bb}


def isolate(src_path, dst_path, offset_mm=0.20, frame_rect=None,
            margin_mm=2.0, invert=True):
    """Full pipeline. Returns a stats dict. Raises TransformError on trouble."""
    work = tempfile.mkdtemp(prefix="klb_")
    try:
        shutil.copyfile(src_path, os.path.join(work, "in.svg"))
        union(work, "in.svg", "u.svg")
        _, _, copper_subs = _counts(work, "u.svg")
        dilate(work, "u.svg", "d.svg", offset_mm)
        if not invert:
            shutil.copyfile(os.path.join(work, "d.svg"), dst_path)
            d, n, s = _counts(work, "d.svg")
            return {"paths": n, "subpaths": s, "copper_subpaths": copper_subs,
                    "bbox_mm": inkscape.drawing_bbox_mm(work, "d.svg"),
                    "inverted": False}
        if frame_rect is None:
            bb = inkscape.drawing_bbox_mm(work, "d.svg")
            if bb is None:
                raise TransformError("Copper layer appears empty; no frame.")
            frame_rect = (bb[0] - margin_mm, bb[1] - margin_mm,
                          bb[2] + 2 * margin_mm, bb[3] + 2 * margin_mm)
        add_frame(work, "d.svg", "f.svg", frame_rect)
        difference(work, "f.svg", "o.svg")
        stats = _validate(work, "o.svg", frame_rect, copper_subs)
        stats["inverted"] = True
        stats["frame_mm"] = frame_rect
        shutil.copyfile(os.path.join(work, "o.svg"), dst_path)
        return stats
    finally:
        shutil.rmtree(work, ignore_errors=True)
