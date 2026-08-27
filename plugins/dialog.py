"""Settings dialog. Uses the wx that KiCad already ships."""
import os

import wx

INTRO = ("Plots the board's copper and turns it into laser artwork for "
         "LightBurn. Each output kind gets its own colour so LightBurn "
         "assigns it to a separate layer.\n"
         "Import the single LB_<side>.svg it writes -- LightBurn centres "
         "each import, so importing parts separately loses the shared "
         "origin. Hover any field for details.")

TIPS = {
    "outdir": "Folder the SVGs are written to.\n\n"
              "Created if it does not exist. ~ and $VARS are expanded, and a "
              "relative path is taken as relative to the board file -- not to "
              "wherever KiCad was launched from. Existing files with the same "
              "names are overwritten.",
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
    "maskf":  "Emit the F.Cu solder mask OPENINGS on their own layer "
              "(magenta), for ablating mask off a coated board.\n\n"
              "KiCad's F.Mask layer already describes where mask is absent, "
              "so it is used as-is -- positive, and with no moat offset, "
              "because the opening should match the pad.",
    "maskb":  "Same as F.Mask removal, for the back side. Mirrored about X=0 "
              "along with the rest of the back artwork.",
    "keep":   "Also write the intermediate SVGs (raw plots, per-layer parts) "
              "next to the combined file.\n\n"
              "Off by default: those parts must NOT be imported separately, "
              "because LightBurn centres each import and the shared origin is "
              "lost. Turn this on only to debug a bad export.",
    "mode_iso": "Ablate the copper BETWEEN the traces, leaving the traces "
                "standing. This is the direct-ablation route and produces a "
                "finished board straight off the laser.\n\n"
                "The moat offset above controls how wide those gaps are cut.",
    "mode_pos": "Ablate the trace shapes themselves, producing positive "
                "artwork rather than the gaps.\n\n"
                "This is for the fallback route: spray the board black, "
                "ablate this pattern as an etch resist, then etch. The output "
                "is a mask, NOT a finished board -- burning it expecting "
                "isolation would remove exactly the copper you meant to keep.",
    "_invert_old": "ON  -- burn the isolation moats around the copper, leaving the "
              "traces standing. This is direct copper ablation.\n\n"
              "OFF -- burn the copper shapes themselves, giving positive "
              "artwork for the spray-black / ablate-resist / etch fallback.\n\n"
              "These are opposites: running the wrong one will destroy a "
              "board.",
}


def _tip(ctrl, text):
    """Set a tooltip on a control AND its children.

    wx.SpinCtrlDouble is composite: on macOS the pointer sits over its inner
    text field, which does not inherit the parent's tooltip, so a tip set only
    on the control never appears.
    """
    ctrl.SetToolTip(text)
    for kid in ctrl.GetChildren():
        kid.SetToolTip(text)


class SettingsDialog(wx.Dialog):
    def __init__(self, parent, default_dir):
        wx.Dialog.__init__(self, parent, title="PCB -> LightBurn isolation artwork")
        pane = wx.BoxSizer(wx.VERTICAL)

        intro = wx.StaticText(self, label=INTRO)
        intro.Wrap(620)
        pane.Add(intro, 0, wx.ALL, 10)

        grid = wx.FlexGridSizer(0, 2, 6, 8)
        grid.AddGrowableCol(1, 1)

        lbl_dir = wx.StaticText(self, label="Output folder")
        lbl_dir.SetToolTip(TIPS["outdir"])
        grid.Add(lbl_dir, 0, wx.ALIGN_CENTER_VERTICAL)
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

        lbl_off = wx.StaticText(self, label="Moat offset (mm)")
        lbl_off.SetToolTip(TIPS["offset"])
        grid.Add(lbl_off, 0, wx.ALIGN_CENTER_VERTICAL)
        self.offset = wx.SpinCtrlDouble(self, min=0.0, max=2.0, inc=0.01, initial=0.20)
        self.offset.SetDigits(2)
        _tip(self.offset, TIPS["offset"])
        grid.Add(self.offset)

        lbl_mar = wx.StaticText(self, label="Frame margin (mm)")
        lbl_mar.SetToolTip(TIPS["margin"])
        grid.Add(lbl_mar, 0, wx.ALIGN_CENTER_VERTICAL)
        self.margin = wx.SpinCtrlDouble(self, min=0.0, max=10.0, inc=0.5, initial=1.0)
        self.margin.SetDigits(1)
        _tip(self.margin, TIPS["margin"])
        grid.Add(self.margin)
        pane.Add(grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        box = wx.StaticBoxSizer(wx.VERTICAL, self, "Layers")
        self.front = wx.CheckBox(self, label="F.Cu")
        self.back = wx.CheckBox(self, label="B.Cu (mirrored about X=0)")
        self.drills = wx.CheckBox(self, label="Drills (own LightBurn layer)")
        self.cuts = wx.CheckBox(self, label="Edge.Cuts (own LightBurn layer)")
        self.reg = wx.CheckBox(self, label="Registration holes (own layer)")
        self.maskf = wx.CheckBox(self, label="F.Mask removal (own layer)")
        self.maskb = wx.CheckBox(self, label="B.Mask removal (own layer)")
        for ctrl, key in ((self.front, "front"), (self.back, "back"),
                          (self.drills, "drills"), (self.cuts, "cuts"),
                          (self.reg, "reg"), (self.maskf, "maskf"),
                          (self.maskb, "maskb")):
            ctrl.SetToolTip(TIPS[key])
            box.Add(ctrl, 0, wx.ALL, 3)
        self.front.SetValue(True)
        self.back.SetValue(True)
        self.maskf.SetValue(True)
        self.maskb.SetValue(True)
        pane.Add(box, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

        mode = wx.StaticBoxSizer(wx.VERTICAL, self, "What the laser burns on the copper layer")
        self.mode_iso = wx.RadioButton(
            self, label="Around the traces \u2014 isolation moats",
            style=wx.RB_GROUP)
        iso_hint = wx.StaticText(
            self, label="        Copper between traces is ablated away; the traces "
                        "themselves survive.\n        This is direct copper ablation "
                        "\u2014 the finished board.")
        self.mode_pos = wx.RadioButton(
            self, label="The traces themselves \u2014 positive copper")
        pos_hint = wx.StaticText(
            self, label="        Burns the trace shapes, not the gaps. For the "
                        "spray-black / ablate-resist /\n        etch fallback \u2014 "
                        "an etch mask, not a finished board.")
        for h in (iso_hint, pos_hint):
            h.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        self.mode_iso.SetValue(True)
        self.mode_iso.SetToolTip(TIPS["mode_iso"])
        self.mode_pos.SetToolTip(TIPS["mode_pos"])
        mode.Add(self.mode_iso, 0, wx.ALL, 3)
        mode.Add(iso_hint, 0, wx.BOTTOM, 6)
        mode.Add(self.mode_pos, 0, wx.ALL, 3)
        mode.Add(pos_hint, 0, wx.BOTTOM, 3)
        pane.Add(mode, 0, wx.ALL | wx.EXPAND, 10)

        self.keep = wx.CheckBox(self, label="Keep intermediate files (debugging)")
        self.keep.SetValue(False)
        self.keep.SetToolTip(TIPS["keep"])
        pane.Add(self.keep, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

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
            do_back=self.back.GetValue(), invert=self.mode_iso.GetValue(),
            do_drills=self.drills.GetValue(), do_cuts=self.cuts.GetValue(),
            do_registration=self.reg.GetValue(),
            do_mask_f=self.maskf.GetValue(), do_mask_b=self.maskb.GetValue(),
            keep_intermediates=self.keep.GetValue())
