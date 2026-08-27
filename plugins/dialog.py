"""Settings dialog. Uses the wx that KiCad already ships."""
import os

import wx


class SettingsDialog(wx.Dialog):
    def __init__(self, parent, default_dir):
        wx.Dialog.__init__(self, parent, title="PCB -> LightBurn isolation artwork")
        pane = wx.BoxSizer(wx.VERTICAL)

        grid = wx.FlexGridSizer(0, 2, 6, 8)
        grid.AddGrowableCol(1, 1)

        grid.Add(wx.StaticText(self, label="Output folder"), 0, wx.ALIGN_CENTER_VERTICAL)
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.dir_ctrl = wx.TextCtrl(self, value=default_dir, size=(320, -1))
        browse = wx.Button(self, label="...", size=(32, -1))
        browse.Bind(wx.EVT_BUTTON, self.on_browse)
        row.Add(self.dir_ctrl, 1, wx.EXPAND)
        row.Add(browse, 0, wx.LEFT, 4)
        grid.Add(row, 1, wx.EXPAND)

        grid.Add(wx.StaticText(self, label="Moat offset (mm)"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.offset = wx.SpinCtrlDouble(self, min=0.0, max=2.0, inc=0.01, initial=0.20)
        self.offset.SetDigits(2)
        grid.Add(self.offset)

        grid.Add(wx.StaticText(self, label="Frame margin (mm)"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.margin = wx.SpinCtrlDouble(self, min=0.0, max=10.0, inc=0.5, initial=1.0)
        self.margin.SetDigits(1)
        grid.Add(self.margin)
        pane.Add(grid, 0, wx.ALL | wx.EXPAND, 10)

        box = wx.StaticBoxSizer(wx.VERTICAL, self, "Layers")
        self.front = wx.CheckBox(self, label="F.Cu")
        self.back = wx.CheckBox(self, label="B.Cu (mirrored about X=0)")
        self.drills = wx.CheckBox(self, label="Drills (own LightBurn layer)")
        self.cuts = wx.CheckBox(self, label="Edge.Cuts (own LightBurn layer)")
        self.reg = wx.CheckBox(self, label="Registration holes (own layer)")
        self.front.SetValue(True)
        for c in (self.drills, self.cuts, self.reg):
            c.SetValue(True)
        for c in (self.front, self.back, self.drills, self.cuts, self.reg):
            box.Add(c, 0, wx.ALL, 3)
        pane.Add(box, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

        self.invert = wx.CheckBox(self, label="Invert: cut isolation moats (uncheck for positive copper)")
        self.invert.SetValue(True)
        pane.Add(self.invert, 0, wx.ALL, 10)

        btns = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        if btns:
            pane.Add(btns, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizerAndFit(pane)

    def on_browse(self, _evt):
        dlg = wx.DirDialog(self, "Output folder", self.dir_ctrl.GetValue())
        if dlg.ShowModal() == wx.ID_OK:
            self.dir_ctrl.SetValue(dlg.GetPath())
        dlg.Destroy()

    def values(self):
        return dict(
            outdir=self.dir_ctrl.GetValue(), offset_mm=self.offset.GetValue(),
            margin_mm=self.margin.GetValue(), do_front=self.front.GetValue(),
            do_back=self.back.GetValue(), invert=self.invert.GetValue(),
            do_drills=self.drills.GetValue(), do_cuts=self.cuts.GetValue(),
            do_registration=self.reg.GetValue())
