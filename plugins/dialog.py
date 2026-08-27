"""Settings dialog. Uses the wx that KiCad already ships."""
import os

import wx

INTRO = ("Plots the board's copper and turns it into laser artwork for "
         "LightBurn. Each output kind gets its own colour so LightBurn "
         "assigns it to a separate layer. Hover any field for details.")

TIPS = {
    "outdir": "Folder the SVGs are written to.\n\n"
              "Defaults to the folder holding the .kicad_pcb. Existing files "
              "with the same names are overwritten.",
    "offset": "How far the isolation moat is grown outward from the copper "
              "edge, in millimetres.\n\n"
              "This is the knob for your laser kerf -- it does not touch the "
              "board file, so you can retune it between burns without a "
              "round trip through KiCad. 0.20mm is a reasonable start; "
              "increase it if adjacent traces are still bridging.",
    "margin": "How far the burn region extends past the board outline, in "
              "millimetres.\n\n"
              "Only used when Invert is on: it sizes the rectangle the copper "
              "is subtracted from, so the moat continues a little way beyond "
              "the edge of the board rather than stopping exactly at it.",
    "front":  "Export the front copper layer (F.Cu).",
    "back":   "Export the back copper layer (B.Cu), mirrored about X=0.\n\n"
              "X=0 is the drill/place origin, so the artwork matches a "
              "left-right flip of the blank on the registration pins. "
              "KiCad's own mirror flips about the page centre instead, which "
              "would not register.",
    "drills": "Emit vias and through-hole pads as circles on their own "
              "LightBurn layer (red).\n\n"
              "They share the drill/place origin with the copper, so they "
              "line up without any manual alignment.",
    "cuts":   "Emit the board outline on its own LightBurn layer (blue), for "
              "cutting the finished board free.\n\n"
              "Mirrored automatically for the back side.",
    "reg":    "Holes lying outside the board outline are treated as dowel / "
              "registration features and put on their own layer (green).\n\n"
              "Cut these first and pin the blank before the isolation pass, "
              "so it cannot shift mid-burn or between sides.",
    "invert": "ON  -- burn the isolation moats around the copper, leaving the "
              "traces standing. This is direct copper ablation.\n\n"
              "OFF -- burn the copper shapes themselves, giving positive "
              "artwork for the spray-black / ablate-resist / etch fallback.\n\n"
              "These are opposites: running the wrong one will destroy a "
              "board.",
}


class SettingsDialog(wx.Dialog):
    def __init__(self, parent, default_dir):
        wx.Dialog.__init__(self, parent, title="PCB -> LightBurn isolation artwork")
        pane = wx.BoxSizer(wx.VERTICAL)

        intro = wx.StaticText(self, label=INTRO)
        intro.Wrap(620)
        pane.Add(intro, 0, wx.ALL, 10)

        grid = wx.FlexGridSizer(0, 2, 6, 8)
        grid.AddGrowableCol(1, 1)

        grid.Add(wx.StaticText(self, label="Output folder"), 0, wx.ALIGN_CENTER_VERTICAL)
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.dir_ctrl = wx.TextCtrl(self, value=default_dir, size=(560, -1))
        self.dir_ctrl.SetToolTip(TIPS["outdir"] + "\n\n" + default_dir)
        self.dir_ctrl.SetInsertionPointEnd()
        browse = wx.Button(self, label="...", size=(36, -1))
        browse.Bind(wx.EVT_BUTTON, self.on_browse)
        browse.SetToolTip("Choose the output folder")
        row.Add(self.dir_ctrl, 1, wx.EXPAND)
        row.Add(browse, 0, wx.LEFT, 4)
        grid.Add(row, 1, wx.EXPAND)

        grid.Add(wx.StaticText(self, label="Moat offset (mm)"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.offset = wx.SpinCtrlDouble(self, min=0.0, max=2.0, inc=0.01, initial=0.20)
        self.offset.SetDigits(2)
        self.offset.SetToolTip(TIPS["offset"])
        grid.Add(self.offset)

        grid.Add(wx.StaticText(self, label="Frame margin (mm)"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.margin = wx.SpinCtrlDouble(self, min=0.0, max=10.0, inc=0.5, initial=1.0)
        self.margin.SetDigits(1)
        self.margin.SetToolTip(TIPS["margin"])
        grid.Add(self.margin)
        pane.Add(grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        box = wx.StaticBoxSizer(wx.VERTICAL, self, "Layers")
        self.front = wx.CheckBox(self, label="F.Cu")
        self.back = wx.CheckBox(self, label="B.Cu (mirrored about X=0)")
        self.drills = wx.CheckBox(self, label="Drills (own LightBurn layer)")
        self.cuts = wx.CheckBox(self, label="Edge.Cuts (own LightBurn layer)")
        self.reg = wx.CheckBox(self, label="Registration holes (own layer)")
        for ctrl, key in ((self.front, "front"), (self.back, "back"),
                          (self.drills, "drills"), (self.cuts, "cuts"),
                          (self.reg, "reg")):
            ctrl.SetToolTip(TIPS[key])
            box.Add(ctrl, 0, wx.ALL, 3)
        self.front.SetValue(True)
        for c in (self.drills, self.cuts, self.reg):
            c.SetValue(True)
        pane.Add(box, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

        self.invert = wx.CheckBox(
            self, label="Invert: cut isolation moats (uncheck for positive copper)")
        self.invert.SetValue(True)
        self.invert.SetToolTip(TIPS["invert"])
        pane.Add(self.invert, 0, wx.ALL, 10)

        btns = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        if btns:
            pane.Add(btns, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizerAndFit(pane)
        self.SetMinSize(self.GetSize())

    def on_browse(self, _evt):
        dlg = wx.DirDialog(self, "Output folder", self.dir_ctrl.GetValue())
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self.dir_ctrl.SetValue(path)
            self.dir_ctrl.SetToolTip(TIPS["outdir"] + "\n\n" + path)
            self.dir_ctrl.SetInsertionPointEnd()
        dlg.Destroy()

    def values(self):
        return dict(
            outdir=self.dir_ctrl.GetValue(), offset_mm=self.offset.GetValue(),
            margin_mm=self.margin.GetValue(), do_front=self.front.GetValue(),
            do_back=self.back.GetValue(), invert=self.invert.GetValue(),
            do_drills=self.drills.GetValue(), do_cuts=self.cuts.GetValue(),
            do_registration=self.reg.GetValue())
