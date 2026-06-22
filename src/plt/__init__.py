"""
plt -- Tecplot-free reading / conversion / rendering of FlexFlow binary .plt output.

Replaces the old pytecplot / Tecplot-360 backend with pure-Python tools:

  fxplt    parse the #!TDV112 binary directly (numpy only)
  convert  .plt -> .vtu (meshio) + a size / element-type audit
  camera   load a saved camera frame (.yml / ParaView .pvsm / .py)
  render   isosurface PNGs via pyvista (optional dependency, imported lazily)

Only `render` needs pyvista/vtk; info / extract / convert need just numpy + meshio.
"""
from .fxplt import PltFile, NPE, ZTYPE_VTK, VOLUME_ZTYPES  # noqa: F401
