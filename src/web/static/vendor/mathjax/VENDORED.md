# Vendored MathJax v2.7.9 (trimmed)

Self-hosted (not a CDN) so the LaTeX style-sidebar checkbox keeps working on an
air-gapped compute node like the rest of this app. The upstream `mathjax@2.7.9`
npm package is ~63 MB / ~3150 files; this tree is trimmed to ~2.7 MB / ~210
files by keeping only what `MathJax.js?config=TeX-MML-AM_SVG` actually loads:

- **SVG output only** — no web fonts to self-host correctly (CommonHTML/
  HTML-CSS output needs woff/eot/svg font *files*; SVG output computes glyph
  paths from JS path data already bundled in `jax/output/SVG/fonts/TeX/`).
  Removed the other output jax (`HTML-CSS`, `NativeMML`, `PreviewHTML`,
  `PlainSource`, `CommonHTML`) and the 6 non-default SVG font families
  (kept only `TeX/`).
- **One config** — kept `config/TeX-MML-AM_SVG.js`, removed the ~30 other
  standard configs (`AM_HTMLorMML`, `MML-CHTML`, etc.) this app never asks for.
- **English only** — `localization/` trimmed from ~120 locales to `en/`,
  matching the rest of this app's UI.
- **Removed** `unpacked/` (a second, non-minified copy of everything),
  `fonts/HTML-CSS` (unused output format's fonts), `extensions/a11y`
  (screen-reader extensions), and AsciiMath input (not used; only TeX input
  is needed here).

To re-vendor at a newer v2.x release: `npm pack mathjax@<version>`, unpack,
and repeat the trims above -- or copy `config/`, `jax/{element,input/{TeX,
MathML},output/SVG}`, `extensions/` (minus `a11y`, `HTML-CSS`,
`asciimath2jax.js`), `localization/en/`, and `MathJax.js` from the fresh
package into a new tree built the same way.
