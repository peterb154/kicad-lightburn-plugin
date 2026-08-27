"""KiCad action plugin entry point."""
import os
import traceback

import pcbnew
import wx

from . import dialog, export, inkscape, transform, plot


class LightburnIsolationPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "LightBurn isolation artwork"
        self.category = "Fabrication"
        self.description = ("Export laser-ready isolation (or positive copper) "
                            "SVG artwork for LightBurn")
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "resources", "icon.png")

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
