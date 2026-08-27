"""Tie plotting, the isolation transform and layer colouring together."""
import os

import pcbnew

try:
    from . import plot, transform, drills, layers
except ImportError:
    import plot, transform, drills, layers

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

    for name, do_it, mirror in (("F.Cu", opt.do_front, False),
                                ("B.Cu", opt.do_back, True)):
        if not do_it:
            continue
        tag = name.replace(".", "_")
        # Always plot UNMIRRORED. KiCad's SetMirror flips about the page
        # centre, not X=0; the X=0 flip is applied inside transform.isolate.
        # Doing both would double-mirror the copper off the frame entirely.
        raw = plot.plot_layer(board, SIDES[name], opt.outdir, tag, mirror=False)
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
    return written
