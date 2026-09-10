# Vendored VTK.js v36.14.2 (UMD build, untrimmed)

Self-hosted (not a CDN) for the same reason as `vendor/mathjax`: this app
targets an air-gapped compute node, so every third-party script it loads has
to already be on disk. Powers the Field -> Render dialog's interactive 3-D
mesh viewer (`static/js/meshviewer.js`) -- lazy-loaded on demand, the same
way `plotly-gl3d.min.js` is (`picker.js`'s `ensureGl3d`), only once a `render`
panel actually needs it.

- **Source**: `https://cdn.jsdelivr.net/npm/vtk.js@36.14.2/vtk.min.js`
  (the npm package's own root-level UMD bundle -- its `package.json` names
  this `/vtk.min.js` as the package's `"default"` entry, not a `dist/`
  subpath). BSD-3-Clause (Kitware).
- **Untrimmed** (~2.4 MB): unlike mathjax, vtk.js's single UMD file is
  already a built, tree-shaken-by-webpack bundle -- there is no equivalent
  "delete the unused input/output formats" step available at the vendoring
  stage the way mathjax's raw npm package allowed. `meshviewer.js` only ever
  exercises a small slice of it (`vtkXMLPolyDataReader`, `vtkOpenGLRenderWindow`,
  `vtkRenderWindowInteractor`, `vtkMapper`/`vtkActor`, `vtkColorTransferFunction`)
  but the bundle ships as one file regardless.
- **To re-vendor at a newer version**: fetch
  `https://cdn.jsdelivr.net/npm/vtk.js@<version>/vtk.min.js` and replace
  `vtk.min.js` in this directory; nothing else in this tree needs to change.
