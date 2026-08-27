"""KiCad action plugin entry point."""
import os
import traceback

import pcbnew
import wx

from . import dialog, export, inkscape, transform, plot


IDENTIFIER = "com.github.peterb154.kicad-lightburn-plugin"


def _find_icon():
    """Locate icon.png across dev-symlink and PCM install layouts.

    A dev symlink points at the repo's plugins/ dir, so resources/ is a
    sibling of the repo root; PCM instead installs it to
    3rdparty/resources/<identifier>/. A missing icon must not break loading.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    real = os.path.dirname(os.path.realpath(__file__))
    for cand in (
        os.path.join(os.path.dirname(real), "resources", "icon.png"),
        os.path.join(os.path.dirname(here), "resources", "icon.png"),
        os.path.join(here, "icon.png"),
        os.path.join(os.path.dirname(os.path.dirname(here)),
                     "resources", IDENTIFIER, "icon.png"),
    ):
        if os.path.isfile(cand):
            return cand
    return ""


class LightburnIsolationPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "LightBurn isolation artwork"
        self.category = "Fabrication"
        self.description = ("Export laser-ready isolation (or positive copper) "
                            "SVG artwork for LightBurn")
        self.show_toolbar_button = True
        self.icon_file_name = _find_icon()

    def Run(self):
        board = pcbnew.GetBoard()
        try:
            inkscape.find_inkscape()
        except inkscape.InkscapeError as e:
            wx.MessageBox(str(e), "Inkscape not found", wx.OK | wx.ICON_ERROR)
            return

        default_dir = os.path.dirname(board.GetFileName() or "") or os.path.expanduser("~")
        dlg = dialog.SettingsDialog(None, default_dir)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        vals = dlg.values()
        dlg.Destroy()

        lines = []
        try:
            written = export.run(board, export.Options(**vals), log=lines.append)
        except (transform.TransformError, plot.PlotError, inkscape.InkscapeError) as e:
            wx.MessageBox("%s\n\nNothing was written." % e,
                          "Export failed", wx.OK | wx.ICON_ERROR)
            return
        except Exception:
            wx.MessageBox(traceback.format_exc(), "Unexpected error",
                          wx.OK | wx.ICON_ERROR)
            return

        wx.MessageBox("\n".join(lines) + "\n\nWrote:\n" +
                      "\n".join(os.path.basename(w) for w in written),
                      "Export complete", wx.OK | wx.ICON_INFORMATION)
