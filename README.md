# KiCad → LightBurn isolation artwork

A KiCad 10 action plugin that turns the open board into laser-ready SVG
artwork for LightBurn. Instead of clearing all non-trace copper, it ablates
**isolation moats** around the traces, so only a thin border burns.

Built for a ComMarker Omni XE (355nm UV galvo) driven from LightBurn.

## What it does

1. **Union** — KiCad plots traces as *stroked* paths with no fillable interior,
   one shape per segment and pad. `object-stroke-to-path` gives them real
   outlines, then `path-union` collapses them into a single path.
2. **Dilate** — grows the copper outward by the moat offset (default 0.20mm).
3. **Frame** — injects a board-sized rect at the bottom of the z-order.
4. **Difference** — frame minus copper leaves exactly the isolation regions.

Output layers are colour-separated. SVG has no native layer concept, and
LightBurn maps geometry to layers by **colour** alone -- it ignores `id`,
`<title>` and Inkscape's layer labels. So every colour here is an exact
LightBurn palette entry, which is what makes the assignment deterministic:

| Layer | Colour | LightBurn |
|-------|---------|-----------|
| Copper isolation | `#000000` | C00 |
| Edge cuts | `#0000FF` | C01 |
| Drills | `#FF0000` | C02 |
| Registration holes | `#00E000` | C03 |
| Silkscreen | `#00E0E0` | C06 |
| Solder mask openings | `#FF00FF` | C07 |

The groups also carry `<title>` and Inkscape layer labels. LightBurn ignores
both, but they make the file legible if you open it in Inkscape or read the
XML. The export report lists which C-layer each output landed on.

F.Mask / B.Mask are KiCad's *mask openings* -- the regions where solder mask
is absent -- so they are emitted positive and with no moat offset, ready to
ablate mask off a coated board. They mirror with the rest of the back
artwork.

F.Silkscreen / B.Silkscreen are also emitted positive with no offset, for
marking legends. Reference designators are plotted, and silk is clipped out
of mask openings so it never marks a bare pad. Both are off by default.

Uncheck **Invert** to emit positive copper artwork instead, for a
spray-black / ablate-resist / etch workflow.

## Requirements

- KiCad 10.x with its bundled Python
- Inkscape 1.x — found at `/Applications/Inkscape.app/Contents/MacOS/inkscape`,
  on `PATH`, or via `$KLB_INKSCAPE`

## Install (development)

```sh
ln -s "$PWD" ~/Documents/KiCad/10.0/3rdparty/plugins/kicad-lightburn-plugin
```

Then **Tools → External Plugins → Refresh Plugins**.

Output defaults to a `Production/` folder beside the board file, created on
export. Change `DEFAULT_SUBDIR` in `plugins/export.py` to use a different
convention.

## Importing into LightBurn

**Import `LB_<side>.svg` — the combined file.** It holds every
colour-separated layer already registered against the drill/place origin,
and it is the only thing the export writes. Intermediates are built in a temp
directory and discarded; tick *Keep intermediate files* to keep them for
debugging.

LightBurn centres imported files on the workspace by default, so importing the
individual per-layer SVGs separately places each one independently and throws
the shared origin away. Two ways round it:

- Import the single `LB_*.svg`. Centring then moves every layer together and
  registration survives.
- Or hold **Shift** while importing, which preserves the file's coordinates
  instead of centring.

Every file this plugin writes is given the same page, sized to the artwork and
symmetric about X=0, so a Shift-import lands on-page and the front and mirrored
back land in the same place. Only the viewBox is retargeted; no path data
moves, so the shared origin is intact either way.

## Notes from building this

Three things that are easy to get wrong, all verified against a real board:

- **`path-outset` does not exist.** Inkscape 1.2+ removed the verb system, and
  outset/inset were never ported to actions. The moat offset is instead done by
  stroking the unioned copper by `2 × offset` and re-running stroke-to-path,
  which dilates by exactly `offset` on every side (measured accurate to <1µm).
- **`SetMirror` mirrors about the page, not X=0.** Verified: `x → page_w - x`,
  a 297mm shift on A4. A physical left-right flip about the drill/place origin
  needs a real X=0 mirror, so B.Cu is mirrored with `scale(-1,1)` instead.
- **`selection-ungroup` unwinds only one nesting level.** KiCad nests its plot
  several groups deep; with a single ungroup, `path-union` silently merges less
  than it should (10 subpaths flat vs 20 nested). The pipeline repeats it.

Everything is plotted with `SetUseAuxOrigin(True)`, so copper, drills and edge
cuts all share the drill/place origin.

## Failing loudly

Wrong-polarity artwork that looks plausible will destroy a board, so the
difference stage is checked: a real boolean collapses everything into exactly
one `<path>` carrying the copper islands as subpaths. Counting only paths is
not enough — the frame is a `<rect>`, so a skipped difference leaves one path
and the right bounding box, and passes a naive check. If validation fails,
nothing is written.

## Credit

Inspired by [Bromus365/Kicad_Lightburn_Plugin](https://github.com/Bromus365/Kicad_Lightburn_Plugin)
(MIT), which covers the plot-and-union path on Windows. The isolation
inversion, moat offset, X=0 mirroring and layer separation here are new.

The toolbar icon is LightBurn's own application icon, used to mark this as a
LightBurn integration. LightBurn and its logo are trademarks of LightBurn
Software LLC; that mark is not covered by this project's MIT licence.

## Licence

MIT
