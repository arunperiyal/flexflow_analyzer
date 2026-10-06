"""run check mesh - count the elements of a Gmsh .msh file and flag triangles.

Reads ASCII MSH 2.x and 4.x directly, so the gmsh Python package is not needed.
"""

from collections import Counter
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import box


# Gmsh element type -> (name, dimension)
ELEMENT_TYPES = {
    1: ('Line 2', 1), 8: ('Line 3', 1), 26: ('Line 4', 1),
    2: ('Triangle 3', 2), 9: ('Triangle 6', 2), 20: ('Triangle 9', 2),
    21: ('Triangle 10', 2), 22: ('Triangle 12', 2), 23: ('Triangle 15', 2),
    24: ('Triangle 15i', 2), 25: ('Triangle 21', 2),
    3: ('Quadrilateral 4', 2), 10: ('Quadrilateral 9', 2), 16: ('Quadrilateral 8', 2),
    4: ('Tetrahedron 4', 3), 11: ('Tetrahedron 10', 3),
    5: ('Hexahedron 8', 3), 12: ('Hexahedron 27', 3), 17: ('Hexahedron 20', 3),
    6: ('Prism 6', 3), 13: ('Prism 18', 3), 18: ('Prism 15', 3),
    7: ('Pyramid 5', 3), 14: ('Pyramid 14', 3), 19: ('Pyramid 13', 3),
    15: ('Point', 0),
}

TRIANGLE_TYPES = {2, 9, 20, 21, 22, 23, 24, 25}


class MeshReadError(Exception):
    pass


def read_msh_counts(path: Path):
    """Return (version, node_count, Counter{element_type: count}) for an ASCII .msh file."""
    version = None
    nodes = None
    counts = Counter()
    found_elements = False

    with open(path, 'r', errors='replace') as f:
        for line in f:
            tag = line.strip()
            if tag == '$MeshFormat':
                fields = next(f).split()
                version = fields[0]
                if len(fields) > 1 and fields[1] != '0':
                    raise MeshReadError("binary .msh files are not supported; "
                                        "write the mesh as ASCII (Mesh.Binary = 0)")
            elif tag == '$Nodes':
                header = next(f).split()
                # 2.x: <numNodes>; 4.x: <numEntityBlocks> <numNodes> <min> <max>
                nodes = int(header[0]) if len(header) == 1 else int(header[1])
            elif tag == '$Elements':
                found_elements = True
                if version is None:
                    raise MeshReadError("$MeshFormat section missing")
                if float(version) >= 4:
                    num_blocks = int(next(f).split()[0])
                    for _ in range(num_blocks):
                        # <entityDim> <entityTag> <elementType> <numElementsInBlock>
                        _, _, etype, n = (int(x) for x in next(f).split()[:4])
                        counts[etype] += n
                        for _ in range(n):
                            next(f)
                else:
                    num = int(next(f).split()[0])
                    for _ in range(num):
                        # <id> <type> <numTags> <tags...> <nodes...>
                        counts[int(next(f).split()[1])] += 1

    if not found_elements:
        raise MeshReadError("no $Elements section found")
    return version, nodes, counts


def resolve_mesh_file(target: Path):
    """A .msh path as given, or <problem>.msh inside a case directory."""
    if target.is_file():
        return target
    if not target.is_dir():
        return None
    from src.core.simflow_config import SimflowConfig
    problem = SimflowConfig.find(target).problem
    if problem and (target / f'{problem}.msh').is_file():
        return target / f'{problem}.msh'
    meshes = sorted(target.glob('*.msh'))
    return meshes[0] if len(meshes) == 1 else None


def check_mesh(target: Path, console: Console) -> bool:
    """Print element counts of the case's mesh; return False if it has triangles or can't be read."""
    msh = resolve_mesh_file(target)
    if msh is None:
        console.print(f"[red]✗[/red] No mesh file found in {target} "
                      "(expected <problem>.msh; run 'run pre' first)")
        return False

    try:
        version, nodes, counts = read_msh_counts(msh)
    except (MeshReadError, ValueError, IndexError, StopIteration) as e:
        console.print(f"[red]✗[/red] Could not read {msh}: {e or 'unexpected end of file'}")
        return False

    console.print()
    console.print(f"[bold cyan]Mesh:[/bold cyan] {msh}  [dim](MSH {version})[/dim]")
    console.print(f"Nodes: {nodes if nodes is not None else '—'}")

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
    table.add_column("Dim", justify="right")
    table.add_column("Element")
    table.add_column("Count", justify="right")

    def _key(etype):
        return (ELEMENT_TYPES.get(etype, ('', 99))[1], etype)

    for etype in sorted(counts, key=_key):
        name, dim = ELEMENT_TYPES.get(etype, (f'type {etype}', None))
        row = (str(dim) if dim is not None else '?', name, str(counts[etype]))
        table.add_row(*row, style="bold red" if etype in TRIANGLE_TYPES else None)
    console.print(table)

    triangles = sum(counts[t] for t in TRIANGLE_TYPES)
    if triangles:
        console.print(f"[bold red]✗ {triangles} triangle element(s) in the mesh[/bold red] — "
                      "fix the .geo (e.g. Recombine) before running simGmshCnvt")
    else:
        console.print("[green]✓ No triangles in the mesh[/green]")
    console.print()
    return triangles == 0
