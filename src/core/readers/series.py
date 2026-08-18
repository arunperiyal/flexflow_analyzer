"""
series.py -- othd/oisd time-history files read as named variables.

Both formats are the same shape: a stream of timesteps, each a `tsId` and a
`time` followed by named blocks. A block is

    <name> <ncomp> <nnodes>
    v v v            <- nnodes lines of ncomp values

and a few names carry their value inline instead (`avePres 3.2e+02`). Which
names appear is a property of the run, not of this code -- a case writes what
its .def asked for -- so the variables are discovered by reading rather than
listed here. That is the whole reason this module exists: the older readers
named `aleDisp` and three integrated quantities in Python, and everything else
in the file was invisible to the CLI.

    meta = scan(paths)                  # what is in there, without the numbers
    data = load(paths, ["vel"], meta)   # only the variables asked for
"""

import os
import re
from pathlib import Path

import numpy as np

# Bookkeeping rather than data: the step's identity, and the counts that
# describe the file. Never offered as variables to plot or tabulate.
STRUCTURAL = {
    "tsId", "time", "mask",
    "nOths", "othId", "othFlag",        # othd
    "nOsfs", "osgId", "osdFlag",        # oisd
}

# name ncomp nnodes -> a block with data lines under it
_BLOCK = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s+(\d+)\s+(\d+)\s*$")
# name value -> the value is on the line itself
_INLINE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s+([-+0-9.][^\s]*)\s*$")

COMPONENT_SUFFIX = ("_x", "_y", "_z")


class VarInfo:
    """One variable's shape, as the file declares it."""

    def __init__(self, name, ncomp, nnodes, inline=False):
        self.name = name
        self.ncomp = ncomp
        self.nnodes = nnodes
        self.inline = inline

    @property
    def columns(self):
        """The column names this variable contributes to a table."""
        if self.ncomp == 1:
            return [self.name]
        if self.ncomp == 3:
            return [self.name + s for s in COMPONENT_SUFFIX]
        return ["%s_%d" % (self.name, i) for i in range(self.ncomp)]

    def __repr__(self):
        return "VarInfo(%s, ncomp=%d, nnodes=%d)" % (self.name, self.ncomp, self.nnodes)


class SeriesMeta:
    """What a set of othd/oisd files holds, without their numbers.

    A file may carry more than one output group -- several `othId`s in an othd,
    several `osgId`s in an oisd -- each its own set of nodes writing its own
    variables at every timestep. One group is the common case and the only one
    these cases have so far, but two probe sets in one file is a thing the
    format allows, and reading only the last of them would be silent and wrong.
    """

    def __init__(self, kind, files, times, tsids, by_group):
        self.kind = kind
        self.files = files
        self.times = np.asarray(times, dtype=float)
        self.tsids = np.asarray(tsids, dtype=int)
        self.by_group = by_group            # group id -> {name: VarInfo}

    @property
    def groups(self):
        """The output groups present, in file order."""
        return sorted(self.by_group)

    @property
    def group_label(self):
        """What this format calls a group."""
        return "osgId" if self.kind == "oisd" else "othId"

    @property
    def default_group(self):
        return self.groups[0] if self.groups else 0

    def variables_of(self, group=None):
        group = self.default_group if group is None else group
        return self.by_group.get(group, {})

    @property
    def variables(self):
        """The default group's variables -- the whole story when there is one."""
        return self.variables_of()

    def nodes_of(self, group=None):
        vars_ = self.variables_of(group)
        counts = {v.nnodes for v in vars_.values() if not v.inline}
        return max(counts) if counts else 1

    @property
    def nodes(self):
        """Nodes per timestep. 1 means the file holds integrated output."""
        return self.nodes_of()

    def integrated_of(self, group=None):
        return self.nodes_of(group) == 1

    @property
    def integrated(self):
        return self.integrated_of()

    def column_names(self, group=None):
        cols = []
        for v in self.variables_of(group).values():
            cols.extend(v.columns)
        return cols


def kind_of(path):
    return "oisd" if str(path).endswith(".oisd") else "othd"


def _scan_file(path, times, tsids, by_group, seen_times):
    """One file's timesteps and variable shapes; numbers are stepped over."""
    with open(path, "r") as fh:
        lines = fh.readlines()

    i, n = 0, len(lines)
    tsid = None
    group = 0
    while i < n:
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        head = line.split(None, 1)[0]
        if head == "tsId":
            tsid = int(line.split()[1])
            i += 1
            continue
        if head in ("othId", "osgId"):
            # Everything after this line belongs to that group, until the next
            # such line. A timestep with several groups repeats its blocks once
            # per group rather than repeating the timestep.
            group = int(line.split()[1])
            i += 1
            continue
        if head == "time":
            t = float(line.split()[1])
            # A restart rewrites times already present rather than appending,
            # the way the older readers did: the later file wins.
            if t not in seen_times:
                seen_times[t] = len(times)
                times.append(t)
                tsids.append(tsid if tsid is not None else -1)
            else:
                tsids[seen_times[t]] = tsid if tsid is not None else -1
            i += 1
            continue

        block = _BLOCK.match(line)
        if block:
            name, ncomp, nnodes = block.group(1), int(block.group(2)), int(block.group(3))
            found = by_group.setdefault(group, {})
            if name not in STRUCTURAL and name not in found:
                found[name] = VarInfo(name, ncomp, nnodes)
            i += 1 + nnodes                 # step over the data
            continue

        inline = _INLINE.match(line)
        if inline:
            name = inline.group(1)
            found = by_group.setdefault(group, {})
            if name not in STRUCTURAL and name not in found:
                found[name] = VarInfo(name, 1, 1, inline=True)
        i += 1


def scan(paths):
    """Read what a set of files holds, without converting their numbers."""
    paths = [str(p) for p in paths]
    if not paths:
        raise ValueError("no files to scan")
    times, tsids, by_group, seen = [], [], {}, {}
    for path in paths:
        _scan_file(path, times, tsids, by_group, seen)
    order = np.argsort(times)
    times = [times[i] for i in order]
    tsids = [tsids[i] for i in order]
    return SeriesMeta(kind_of(paths[0]), paths, times, tsids, by_group or {0: {}})


def _load_file(path, wanted, group, out, seen_times):
    """Fill `out[name][step]` for `wanted`, reading `group` alone."""
    with open(path, "r") as fh:
        lines = fh.readlines()

    i, n = 0, len(lines)
    step = None
    current = 0
    while i < n:
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        head = line.split(None, 1)[0]

        if head == "time":
            step = seen_times.get(float(line.split()[1]))
            i += 1
            continue
        if head in ("othId", "osgId"):
            current = int(line.split()[1])
            i += 1
            continue

        block = _BLOCK.match(line)
        if block:
            name, ncomp, nnodes = block.group(1), int(block.group(2)), int(block.group(3))
            if name in wanted and step is not None and current == group:
                rows = lines[i + 1:i + 1 + nnodes]
                values = np.fromstring(" ".join(rows), sep=" ")
                if values.size == nnodes * ncomp:
                    out[name][step] = values.reshape(nnodes, ncomp)
            i += 1 + nnodes
            continue

        inline = _INLINE.match(line)
        if (inline and inline.group(1) in wanted and step is not None
                and current == group):
            out[inline.group(1)][step] = float(inline.group(2))
        i += 1


def load(paths, names, meta=None, group=None):
    """Arrays for `names`, each shaped (timesteps, nodes, components).

    Only the named variables are converted, and only from the group asked for.
    A case's othd carries six variables over tens of thousands of steps, and a
    table of one is not a reason to parse the other five.
    """
    meta = meta or scan(paths)
    group = meta.default_group if group is None else group
    if group not in meta.by_group:
        raise KeyError("no %s %s in these files. Present: %s"
                       % (meta.group_label, group,
                          ", ".join(str(g) for g in meta.groups)))
    variables = meta.variables_of(group)
    unknown = [n for n in names if n not in variables]
    if unknown:
        raise KeyError("not in these files: %s. Available: %s"
                       % (", ".join(unknown), ", ".join(sorted(variables))))

    nsteps = len(meta.times)
    out = {}
    for name in names:
        info = variables[name]
        out[name] = np.full((nsteps, info.nnodes, info.ncomp), np.nan)

    seen_times = {t: i for i, t in enumerate(meta.times)}
    wanted = set(names)
    for path in meta.files:
        _load_file(path, wanted, group, out, seen_times)
    return out
