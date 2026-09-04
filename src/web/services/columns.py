"""services/columns.py — map a VarInfo.columns name back to (variable, component).

Shared by /history and /export: both need to turn "aleDisp_y" back into
("aleDisp", 1) to slice the (nsteps, nnodes, ncomp) array series.load() hands
back.
"""


def column_map(meta, group) -> dict:
    """{column name: (variable name, component index)} for one group."""
    mapping = {}
    for var in meta.variables_of(group).values():
        for idx, col in enumerate(var.columns):
            mapping[col] = (var.name, idx)
    return mapping
