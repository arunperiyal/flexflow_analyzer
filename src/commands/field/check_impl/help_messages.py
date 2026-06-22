"""Help text for `field check`."""


def print_check_help():
    print("""
flexflow field check <file.vtu|.vtk|.vtp>

Validate a VTK file produced by `field convert` / `field extract`: confirm it
reads back, and report points, cells (by type), bounds, and each point-data
array's range -- flagging empty files or NaN/Inf values. Exits non-zero if the
file has problems.

  .vtu / .vtk   read with meshio (no extra deps)
  .vtp          read with pyvista

Options:
  -v, --verbose
  -h, --help

Examples:
  flexflow field check results.vtk
  flexflow field check field.vtu
""")
