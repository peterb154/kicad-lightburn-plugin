"""Tie plotting, the isolation transform and layer colouring together."""
import os

import pcbnew

try:
    from . import plot, transform, drills, layers, inkscape
except ImportError:
    import plot, transform, drills, layers, inkscape

SIDES = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}


class Options(object):
    def __init__(self, outdir, offset_mm=0.20, margin_mm=1.0, do_front=True,
                 do_back=False, invert=True, do_drills=True, do_cuts=True,
                 do_registration=True):
        self.outdir = outdir
        self.offset_mm = offset_mm
        self.margin_mm = margin_mm
        self.do_front = do_front
        self.do_back = do_back
        self.invert = invert
        self.do_drills = do_drills
        self.do_cuts = do_cuts
        self.do_registration = do_registration


def srcs_paths(srcs):
    return [p for _, p in srcs]


def run(board, opt, log=None):
    log = log or (lambda m: None)
    if not (opt.do_front or opt.do_back):
        raise transform.TransformError("No copper layer selected.")
    if not os.path.isdir(opt.outdir):
        os.makedirs(opt.outdir)

    frame = plot.board_frame_mm(board, opt.margin_mm)
    ax, ay = plot.aux_origin_mm(board)
    log("Board frame %.2f x %.2f mm; aux origin %.3f, %.3f mm"
        % (frame[2], frame[3], ax, ay))

    cuts_svg = plot.plot_layer(board, pcbnew.Edge_Cuts, opt.outdir, "Edge_Cuts") \
        if opt.do_cuts else None
    written = []
    produced = []

    for name, do_it, mirror in (("F.Cu", opt.do_front, False),
                                ("B.Cu", opt.do_back, True)):
        if not do_it:
            continue
        tag = name.replace(".", "_")
        # Always plot UNMIRRORED. KiCad's SetMirror flips about the page
        # centre, not X=0; the X=0 flip is applied inside transform.isolate.
        # Doing both would double-mirror the copper off the frame entirely.
        raw = plot.plot_layer(board, SIDES[name], opt.outdir, tag, mirror=False)
        produced.append(raw)
        art = os.path.join(opt.outdir, "%s_%s.svg" %
                           (tag, "iso" if opt.invert else "positive"))
        fr = frame
        if mirror:
            fr = (-(frame[0] + frame[2]), frame[1], frame[2], frame[3])
        st = transform.isolate(raw, art, opt.offset_mm,
                               frame_rect=fr if opt.invert else None,
                               invert=opt.invert)
        log("%s: %s, %d subpaths (%d copper islands)"
            % (name, "isolation" if opt.invert else "positive copper",
               st["subpaths"], st["copper_subpaths"]))

        srcs = [("copper", art)]
        if opt.do_drills or opt.do_registration:
            inside, reg = drills.partition(board, frame)
            if opt.do_drills and inside:
                d, n = drills.write_svg(board, raw,
                                        os.path.join(opt.outdir, tag + "_drills.svg"),
                                        mirror_about_x0=mirror, holes=inside)
                srcs.append(("drills", d))
                log("  drills: %d holes" % n)
            if opt.do_registration and reg:
                d, n = drills.write_svg(board, raw,
                                        os.path.join(opt.outdir, tag + "_reg.svg"),
                                        mirror_about_x0=mirror, holes=reg)
                srcs.append(("fiducials", d))
                log("  registration: %d holes outside the board outline" % n)
        if cuts_svg:
            # Cutting the outline from the back means the cut path must be
            # mirrored about X=0 too, or it will not register with the flip.
            if mirror:
                cuts_svg_side = os.path.join(opt.outdir, tag + "_cuts.svg")
                transform.mirror_file(cuts_svg, cuts_svg_side)
            else:
                cuts_svg_side = cuts_svg
            srcs.append(("cuts", cuts_svg_side))

        combined = os.path.join(opt.outdir, "LB_%s.svg" % tag)
        _, counts = layers.combine(srcs, combined)
        log("  -> %s  %s" % (os.path.basename(combined), counts))
        written.append(combined)
        produced.extend(srcs_paths(srcs) + [combined])

    # One shared page for every file, symmetric about X=0 so the front and
    # the mirrored back land in the same place.
    boxes = [b for b in (inkscape.drawing_bbox_mm(os.path.dirname(f),
                                                  os.path.basename(f))
                         for f in written) if b]
    if boxes:
        xs = max(max(abs(b[0]), abs(b[0] + b[2])) for b in boxes)
        y0 = min(b[1] for b in boxes)
        y1 = max(b[1] + b[3] for b in boxes)
        pad = 1.0
        box = (-xs - pad, y0 - pad, 2 * (xs + pad), (y1 - y0) + 2 * pad)
        for f in produced:
            if os.path.isfile(f):
                layers.set_canvas(f, box)
        log("Shared page: %.2f x %.2f mm, origin at page centre X"
            % (box[2], box[3]))
    return written
