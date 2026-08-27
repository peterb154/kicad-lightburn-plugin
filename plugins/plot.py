"""Plot board layers to SVG via pcbnew's PLOT_CONTROLLER.

Everything is plotted with SetUseAuxOrigin(True) so the copper artwork, the
drill artwork and KiCad's Excellon output all share the drill/place origin.
That origin is the datum the whole fixture flow is built on.
"""
import os

import pcbnew


class PlotError(RuntimeError):
    pass


def aux_origin_mm(board):
    ds = board.GetDesignSettings()
    for attr in ("GetAuxOrigin", "m_AuxOrigin"):
        o = getattr(ds, attr, None)
        if o is None:
            continue
        o = o() if callable(o) else o
        return pcbnew.ToMM(o.x), pcbnew.ToMM(o.y)
    return 0.0, 0.0


def board_frame_mm(board, margin_mm=0.0):
    """Board outline bbox in mm, relative to the aux origin."""
    bb = board.GetBoardEdgesBoundingBox()
    ax, ay = aux_origin_mm(board)
    x = pcbnew.ToMM(bb.GetX()) - ax
    y = pcbnew.ToMM(bb.GetY()) - ay
    w = pcbnew.ToMM(bb.GetWidth())
    h = pcbnew.ToMM(bb.GetHeight())
    if w <= 0 or h <= 0:
        raise PlotError(
            "Board outline is empty -- Edge.Cuts has no closed shape, so the "
            "isolation frame cannot be sized. Draw a board outline first.")
    return (x - margin_mm, y - margin_mm, w + 2 * margin_mm, h + 2 * margin_mm)


def plot_layer(board, layer_id, outdir, suffix, mirror=False):
    """Plot one layer to SVG. Returns the file path."""
    ctl = pcbnew.PLOT_CONTROLLER(board)
    opt = ctl.GetPlotOptions()
    opt.SetOutputDirectory(outdir)
    opt.SetUseAuxOrigin(True)      # share the drill/place datum
    opt.SetPlotFrameRef(False)     # no page border
    opt.SetPlotValue(False)
    opt.SetPlotReference(False)
    opt.SetMirror(mirror)
    opt.SetNegative(False)
    opt.SetScale(1.0)
    opt.SetDrillMarksType(pcbnew.DRILL_MARKS_NO_DRILL_SHAPE)  # solid copper
    if hasattr(opt, "SetSvgPrecision"):
        try:
            opt.SetSvgPrecision(6)
        except TypeError:
            opt.SetSvgPrecision(6, False)
    ctl.SetColorMode(False)
    if not ctl.OpenPlotfile(suffix, pcbnew.PLOT_FORMAT_SVG, suffix):
        raise PlotError("Could not open plot file for " + suffix)
    ctl.SetLayer(layer_id)
    ok = ctl.PlotLayer()
    path = ctl.GetPlotFileName()
    ctl.ClosePlot()
    if not ok:
        raise PlotError("PlotLayer failed for " + suffix)
    if not os.path.isfile(path):
        raise PlotError("Plot reported success but produced no file: " + path)
    return path
