"""Help text for `field convert`."""


def print_convert_help():
    print("""
flexflow field convert <case> [options]

Convert a binary PLT volume zone to a VTK .vtu (for ParaView / pyvista).
Tecplot-free: parses the PLT directly with numpy and writes with meshio.

Options:
  --timestep N       timestep to convert (default: latest in binary/)
  --zone NAME        zone to export (default: first 3D/volume zone)
  --nen N            force nodes-per-element if the zone type is wrong
                     (e.g. 8 for an 8-node brick mesh mislabelled as 4-node tet)
  --output PATH      output .vtu path (default: alongside the .plt)
  --audit-only       report element type / size consistency; write nothing
  --xmin/--xmax ...  crop to an axis-aligned box before writing (keeps cells
  --ymin/--ymax ...  whose nodes are all inside; any bound may be omitted)
  --zmin/--zmax ...
  -v, --verbose      verbose output
  -h, --help         this help

Examples:
  flexflow field convert myCase
  flexflow field convert myCase --timestep 100 --output field.vtu
  flexflow field convert myCase --audit-only
  flexflow field convert myCase --xmin -1 --xmax 5 --ymin -2 --ymax 2   # near-wake mesh
""")
