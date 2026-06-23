"""Help text for `field check`."""


def print_check_help():
    print("""
flexflow field check <file.vtu|.vtk|.vtp|.pvd>

Validate a file produced by `field convert` / `field extract`: confirm it reads
back, and report points, cells (by type), bounds, and each point-data array's
range -- flagging empty files or NaN/Inf values. Exits non-zero on problems.

Supported inputs:
  .vtu / .vtk   single mesh / point cloud (read with meshio)
  .vtp          point cloud (read with pyvista)
  .pvd          time-series collection: lists the timesteps, verifies every
                referenced member file exists, and summarises one member

Options:
  -v, --verbose
  -h, --help

Examples:
  flexflow field check results.vtk
  flexflow field check snap.vtu
  flexflow field check wake.pvd
""")
