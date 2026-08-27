"""Tie plotting, the isolation transform and layer colouring together.

Every intermediate is built in a temp directory; only the combined
LB_<side>.svg files land in the output folder, because those are the only
ones meant to be imported. Importing the per-layer parts separately loses the
shared origin (LightBurn centres each import), so leaving them lying next to
the real output is a trap. "Keep intermediate files" puts them back for
debugging.
"""
import os
import shutil
import tempfile

import pcbnew

try:
    from . import plot, transform, drills, layers, inkscape
except ImportError:
    import plot, transform, drills, layers, inkscape

SIDES = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
MASKS = {"F.Cu": pcbnew.F_Mask, "B.Cu": pcbnew.B_Mask}


class Options(object):
    def __init__(self, outdir, offset_mm=0.20, margin_mm=1.0, do_front=True,
                 do_back=True, invert=True, do_drills=False, do_cuts=False,
                 do_registration=False, do_mask_f=False, do_mask_b=False,
                 keep_intermediates=False):
        self.outdir = outdir
        self.offset_mm = offset_mm
        self.margin_mm = margin_mm
        self.do_front = do_front
        self.do_back = do_back
        self.invert = invert
        self.do_drills = do_drills
        self.do_cuts = do_cuts
        self.do_registration = do_registration
        self.do_mask_f = do_mask_f
        self.do_mask_b = do_mask_b
        self.keep_intermediates = keep_intermediates


def _build(board, opt, work, log):
    """Produce every SVG inside `work`. Returns (finals, all_files)."""
    frame = plot.board_frame_mm(board, opt.margin_mm)
    ax, ay = plot.aux_origin_mm(board)
    log("Board frame %.2f x %.2f mm; aux origin %.3f, %.3f mm"
        % (frame[2], frame[3], ax, ay))

    cuts_svg = plot.plot_layer(board, pcbnew.Edge_Cuts, work, "Edge_Cuts") \
        if opt.do_cuts else None
    finals, produced = [], ([cuts_svg] if cuts_svg else [])

    for name, do_it, mirror in (("F.Cu", opt.do_front, False),
                                ("B.Cu", opt.do_back, True)):
        if not do_it:
            continue
        tag = name.replace(".", "_")
        # Always plot UNMIRRORED. KiCad's SetMirror flips about the page
        # centre, not X=0; the X=0 flip is applied inside transform.isolate.
        # Doing both would double-mirror the copper off the frame entirely.
        raw = plot.plot_layer(board, SIDES[name], work, tag, mirror=False)
        produced.append(raw)
        art = os.path.join(work, "%s_%s.svg"
                           % (tag, "iso" if opt.invert else "positive"))
        fr = frame
        if mirror:
            fr = (-(frame[0] + frame[2]), frame[1], frame[2], frame[3])
        st = transform.isolate(raw, art, opt.offset_mm,
                               frame_rect=fr if opt.invert else None,
                               invert=opt.invert, mirror=mirror)
        log("%s: %s, %d subpaths (%d copper islands)"
            % (name, "isolation" if opt.invert else "positive copper",
               st["subpaths"], st["copper_subpaths"]))

        srcs = [("copper", art)]
        if (opt.do_mask_f if name == "F.Cu" else opt.do_mask_b):
            # F.Mask/B.Mask are the mask OPENINGS -- the regions to ablate off
            # a coated board -- so they are used positive, with no moat offset.
            raw_mask = plot.plot_layer(board, MASKS[name], work, tag + "_Mask")
            produced.append(raw_mask)
            mask_art = os.path.join(work, tag + "_mask.svg")
            try:
                mst = transform.isolate(raw_mask, mask_art, 0.0,
                                        invert=False, mirror=mirror)
                srcs.append(("mask", mask_art))
                log("  solder mask: %d openings" % mst["subpaths"])
            except transform.TransformError:
                log("  solder mask: no openings on this side, layer skipped")
        if opt.do_drills or opt.do_registration:
            inside, reg = drills.partition(board, frame)
            if opt.do_drills and inside:
                d, n = drills.write_svg(board, raw,
                                        os.path.join(work, tag + "_drills.svg"),
                                        mirror_about_x0=mirror, holes=inside)
                srcs.append(("drills", d))
                log("  drills: %d holes" % n)
            if opt.do_registration and reg:
                d, n = drills.write_svg(board, raw,
                                        os.path.join(work, tag + "_reg.svg"),
                                        mirror_about_x0=mirror, holes=reg)
                srcs.append(("fiducials", d))
                log("  registration: %d holes outside the board outline" % n)
        if cuts_svg:
            # Cutting the outline from the back means the cut path must be
            # mirrored about X=0 too, or it will not register with the flip.
            if mirror:
                side_cuts = os.path.join(work, tag + "_cuts.svg")
                transform.mirror_file(cuts_svg, side_cuts)
            else:
                side_cuts = cuts_svg
            srcs.append(("cuts", side_cuts))

        combined = os.path.join(work, "LB_%s.svg" % tag)
        _, counts = layers.combine(srcs, combined)
        log("  -> %s  %s" % (os.path.basename(combined), counts))
        finals.append(combined)
        produced.extend([p for _, p in srcs] + [combined])

    return finals, produced


def _share_page(finals, produced, log):
    """Give every file one page, symmetric about X=0 so both sides coincide."""
    boxes = [b for b in (inkscape.drawing_bbox_mm(os.path.dirname(f),
                                                  os.path.basename(f))
                         for f in finals) if b]
    if not boxes:
        return
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


def resolve_outdir(board, raw):
    """Normalise a typed output path and create it.

    A typed path may carry surrounding whitespace, a ~, an env var, or be
    relative. os.makedirs expands none of those: "~/out" creates a directory
    literally named "~" in the process cwd, and a relative path lands wherever
    KiCad happens to be running from -- both look to the user like the folder
    was never created.
    """
    path = (raw or "").strip()
    if not path:
        raise transform.TransformError("No output folder given.")
    path = os.path.expanduser(os.path.expandvars(path))
    if not os.path.isabs(path):
        base = os.path.dirname(board.GetFileName() or "") or os.getcwd()
        path = os.path.join(base, path)
    path = os.path.normpath(path)
    if os.path.exists(path) and not os.path.isdir(path):
        raise transform.TransformError(
            "Output path is a file, not a folder:\n" + path)
    try:
        if not os.path.isdir(path):
            os.makedirs(path)
    except OSError as e:
        raise transform.TransformError(
            "Could not create the output folder:\n%s\n\n%s" % (path, e))
    if not os.access(path, os.W_OK):
        raise transform.TransformError("Output folder is not writable:\n" + path)
    return path


def run(board, opt, log=None):
    log = log or (lambda m: None)
    if not (opt.do_front or opt.do_back):
        raise transform.TransformError("No copper layer selected.")
    opt.outdir = resolve_outdir(board, opt.outdir)
    log("Output folder: " + opt.outdir)

    work = tempfile.mkdtemp(prefix="klb_out_")
    try:
        finals, produced = _build(board, opt, work, log)
        _share_page(finals, produced, log)
        keep = produced if opt.keep_intermediates else finals
        written = []
        for src in sorted(set(keep)):
            dst = os.path.join(opt.outdir, os.path.basename(src))
            shutil.copyfile(src, dst)
            written.append(dst)
        if not opt.keep_intermediates:
            log("Wrote only the combined file(s); import these.")
        return sorted(written)
    finally:
        shutil.rmtree(work, ignore_errors=True)
