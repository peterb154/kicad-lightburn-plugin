"""Locate and drive the Inkscape CLI.

All work happens in a temp dir with simple basenames: Inkscape's --actions
string is semicolon/colon delimited, so a real path containing those
characters would silently corrupt the action list.
"""
import os
import shutil
import subprocess

MAC_DEFAULT = "/Applications/Inkscape.app/Contents/MacOS/inkscape"
PX_PER_MM = 96.0 / 25.4


class InkscapeError(RuntimeError):
    pass


def find_inkscape():
    for cand in (os.environ.get("KLB_INKSCAPE"), MAC_DEFAULT, shutil.which("inkscape")):
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    raise InkscapeError(
        "Inkscape not found. Looked for $KLB_INKSCAPE, {}, and 'inkscape' on "
        "PATH.\nInstall Inkscape 1.x from https://inkscape.org and retry.".format(MAC_DEFAULT)
    )


def run_actions(workdir, infile, actions, timeout=300):
    """Run a --actions pipeline. infile is a basename relative to workdir."""
    exe = find_inkscape()
    proc = subprocess.run(
        [exe, infile, "--actions=" + actions],
        cwd=workdir, capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise InkscapeError(
            "inkscape failed (rc={})\nactions: {}\n{}".format(
                proc.returncode, actions, (proc.stderr or "").strip()))
    return proc


def drawing_bbox_mm(workdir, infile):
    """Content bounding box as (x, y, w, h) in mm, or None if empty."""
    exe = find_inkscape()
    out = []
    for flag in ("--query-x", "--query-y", "--query-width", "--query-height"):
        proc = subprocess.run([exe, flag, infile], cwd=workdir,
                              capture_output=True, text=True, timeout=120)
        txt = (proc.stdout or "").strip().splitlines()
        if proc.returncode != 0 or not txt:
            return None
        try:
            out.append(float(txt[0]))
        except ValueError:
            return None
    return tuple(v / PX_PER_MM for v in out)
