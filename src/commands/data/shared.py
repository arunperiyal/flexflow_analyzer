"""
Shared plumbing for `data show`, `data table` and `data stats`.

The three differ in what they print, not in what they read: the same case, the
same othd/oisd files, the same --var / --t1 / --t2 / --node selection. Keeping
that in one place is what lets `data table --var vel_y` and `data stats --var
vel_y` mean the same selection rather than two similar ones.
"""

import glob
import os
import re
import sys
from pathlib import Path

import numpy as np

from ...core.readers import series
from ...utils.colors import Colors

KINDS = ("othd", "oisd")

# Short names. A solver writes camelCase names that are precise and long, and
# `--var aveTurbYPSrf` is not a thing anyone wants to type twice.
#
# The known vocabulary is spelled out rather than derived, because the useful
# short name is not always the mechanical one: aleDisp is the body's motion and
# earns the single letter `d`, while `vel` is the fluid velocity and `aleVel`
# the body's, so the pair cannot both be `v`. Anything not listed falls back to
# camelCase initials, so a run that writes something new still gets one.
SHORT_NAMES = {
    # othd -- per-node history
    "aleDisp": "d", "aleVel": "v", "vel": "u", "pres": "p",
    "eddy": "ed", "orderPar": "op",
    # oisd -- surface output
    "totTrac": "tt", "totMoment": "tm", "totMomFlux": "tmf",
    "totMassFlux": "tmass", "totArea": "ta", "totPower": "tp",
    "aveVel": "av", "avePres": "ap", "aveEddy": "ae", "aveDens": "ad",
    "aveTotPres": "atp", "aveTurbYPSrf": "ay",
    "aveAleDisp": "aad", "aveAleVel": "aav",
}
COMPONENT_LETTERS = {"x": 0, "y": 1, "z": 2}

_CAMEL = re.compile(r"[A-Z]?[a-z0-9]+")


def _derive_short(name):
    """camelCase initials, for a variable not in the table above."""
    parts = _CAMEL.findall(name)
    return "".join(part[0].lower() for part in parts) if parts else None


def short_names(variables):
    """{short name: variable} for one group's variables.

    A short name is dropped rather than guessed at when it would collide with
    another variable's real name or with another short name: two things
    answering to `tmf` is worse than typing one of them out.
    """
    real = {name.lower() for name in variables}
    candidates = {}
    for name in variables:
        short = SHORT_NAMES.get(name) or _derive_short(name)
        if not short or short.lower() in real:
            continue
        candidates.setdefault(short.lower(), []).append(name)
    return {short: names[0] for short, names in candidates.items()
            if len(names) == 1}


def alias_of(name, info, shorts):
    """The short form of a variable's columns, for a listing."""
    for short, full in shorts.items():
        if full == name:
            if info.ncomp == 1:
                return short
            return ", ".join(short + letter for letter in COMPONENT_LETTERS)
    return None


def resolve_case(case_arg, logger):
    """The case directory, or exit with a sentence about why not."""
    if not case_arg:
        return None
    case_dir = Path(case_arg)
    if not case_dir.is_dir():
        logger.error(f"Case directory not found: {case_dir}")
        sys.exit(1)
    return case_dir


def find_files(case_dir, kind):
    """The othd or oisd files of a case, in name order."""
    directory = Path(case_dir) / f"{kind}_files"
    if not directory.is_dir():
        return []
    return sorted(glob.glob(str(directory / f"*.{kind}")))


def out_freq(case_dir):
    """The plt output frequency from simflow.config, or None."""
    try:
        from ...core.simflow_config import SimflowConfig
        return SimflowConfig.find(case_dir).out_freq
    except Exception:
        return None


def scan_kinds(case_dir, kinds, logger):
    """Scan the requested kinds. Returns {kind: SeriesMeta} for those present."""
    metas = {}
    for kind in kinds:
        paths = find_files(case_dir, kind)
        if not paths:
            continue
        try:
            metas[kind] = series.scan(paths)
        except Exception as exc:
            logger.error(f"Could not read the {kind} files: {exc}")
            sys.exit(1)
    return metas


def which_kinds(args):
    """--othd / --oisd -> the kinds to work on. Neither flag means both."""
    othd = bool(getattr(args, "othd", False))
    oisd = bool(getattr(args, "oisd", False))
    if othd and not oisd:
        return ("othd",)
    if oisd and not othd:
        return ("oisd",)
    return KINDS


def split_vars(raw):
    """--var accepts repeats and commas: ['vel,pres', 'eddy'] -> 3 names."""
    names = []
    for item in raw or []:
        names.extend(part.strip() for part in str(item).split(",") if part.strip())
    return names


def resolve_columns(meta, requested, logger, group=None):
    """Requested names -> [(variable, component index, column label)].

    A bare `vel` means all of its components; `vel_y` means that one. Both are
    worth accepting: one is what you ask for when exploring, the other when you
    know which way the flow goes. Short forms (`dy`, `vx`) resolve last, so a
    solver that writes a variable literally called `dy` keeps it.
    """
    variables = meta.variables_of(group)
    lookup = {}
    for name, info in variables.items():
        lookup[name.lower()] = (name, None)
        for idx, col in enumerate(info.columns):
            if info.ncomp > 1:
                lookup[col.lower()] = (name, idx)

    # Short names fill in only where nothing real answers to that spelling.
    for short, full in short_names(variables).items():
        info = variables[full]
        lookup.setdefault(short, (full, None))
        if info.ncomp > 1:
            for letter, idx in COMPONENT_LETTERS.items():
                if idx < info.ncomp:
                    lookup.setdefault(short + letter, (full, idx))

    chosen = []
    for want in requested:
        hit = lookup.get(want.lower())
        if hit is None:
            available = ", ".join(sorted(variables))
            logger.error(f"'{want}' is not in the {meta.kind} files. "
                         f"Available: {available}\n"
                         f"\n        A component can be named too (vel_y), and "
                         f"every variable has a short name -- `data show` lists "
                         f"them.")
            sys.exit(1)
        name, comp = hit
        info = variables[name]
        if comp is None:
            for idx, col in enumerate(info.columns):
                chosen.append((name, idx, col))
        else:
            chosen.append((name, comp, info.columns[comp]))
    # De-duplicate, keeping the order asked for.
    seen, unique = set(), []
    for item in chosen:
        if item[2] not in seen:
            seen.add(item[2])
            unique.append(item)
    return unique


def known_name(meta, name, group=None):
    """Is `name` a variable, a component, or a short name of this group's?

    The mirror of resolve_columns, used to work out which file kind a --var
    belongs to before committing to one.
    """
    variables = meta.variables_of(group)
    low = name.lower()
    for var, info in variables.items():
        if low == var.lower():
            return True
        if info.ncomp > 1 and low in {c.lower() for c in info.columns}:
            return True
    for short, full in short_names(variables).items():
        if low == short:
            return True
        info = variables[full]
        if info.ncomp > 1 and low in {short + letter
                                      for letter in COMPONENT_LETTERS}:
            return True
    return False


def step_mask(meta, t1, t2, logger):
    """Rows inside the --t1/--t2 tsId window. Both None means every row.

    tsId rather than physical time, so that t1/t2 pick out the same steps here
    as they do in `field extract` and `field render`, and so the answer to
    "where does the maximum happen" is already in the units of a PLT filename.

    Open-ended, unlike `field`'s reading of the same two flags: there, a lone
    --t1 names the single step to render, because a render is of one step. Here
    a window is being cut out of a series, and `--t1 3000` on a run that is
    still settling means "from 3000 on", not "step 3000 alone" -- an rms of one
    sample is not a statistic. The window that was used is printed either way.
    """
    lo = int(t1) if t1 is not None else int(meta.tsids.min())
    hi = int(t2) if t2 is not None else int(meta.tsids.max())
    if lo > hi:
        lo, hi = hi, lo
    if t1 is None and t2 is None:
        return np.ones(len(meta.tsids), dtype=bool)
    mask = (meta.tsids >= lo) & (meta.tsids <= hi)
    if not mask.any():
        logger.error(f"No timesteps in tsId range {lo}..{hi}. "
                     f"The {meta.kind} files hold {meta.tsids.min()}..{meta.tsids.max()}.")
        sys.exit(1)
    return mask


def resolve_group(meta, group, logger):
    """Which output group to read. One group means there is nothing to choose."""
    if group is None:
        if len(meta.groups) > 1:
            logger.warning(f"these {meta.kind} files hold {len(meta.groups)} "
                           f"{meta.group_label}s ({', '.join(str(g) for g in meta.groups)}); "
                           f"reading {meta.groups[0]}. --group N picks another.")
        return meta.default_group
    if group not in meta.by_group:
        logger.error(f"No {meta.group_label} {group} in the {meta.kind} files. "
                     f"Present: {', '.join(str(g) for g in meta.groups)}")
        sys.exit(1)
    return group


def resolve_node(meta, node, logger, group=None):
    """The node index to read, checked against how many this group writes."""
    count = meta.nodes_of(group)
    if node is None:
        return 0
    if count == 1 and node != 0:
        # One node is one node, whether that is a surface integral or a single
        # probe point. Either way there is nothing else to ask for.
        logger.warning(f"this {meta.kind} group writes one node, so --node "
                       f"{node} is ignored")
        return 0
    if node < 0 or node >= count:
        logger.error(f"Node {node} does not exist. This {meta.kind} group holds "
                     f"nodes 0..{count - 1}.")
        sys.exit(1)
    return node


def gather(meta, columns, node, mask, group=None):
    """(times, tsids, {label: values}) for the chosen columns, node and rows."""
    names = sorted({name for name, _, _ in columns})
    data = series.load(meta.files, names, meta, group)
    times = meta.times[mask]
    tsids = meta.tsids[mask]
    out = {}
    for name, comp, label in columns:
        out[label] = data[name][mask, node, comp]
    return times, tsids, out


def write_csv(path, times, tsids, values, logger):
    """Write the table to a .csv, creating the directory if it is missing."""
    directory = os.path.dirname(str(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    labels = list(values)
    rows = np.column_stack([tsids, times] + [values[l] for l in labels])
    header = ",".join(["tsId", "time"] + labels)
    np.savetxt(str(path), rows, delimiter=",", header=header, comments="",
               fmt=["%d"] + ["%.12g"] * (rows.shape[1] - 1))
    logger.success(f"wrote {rows.shape[0]} rows -> {path}")


def slice_rows(count, head, tail, has_output):
    """Which row indices to print: --head N, --tail N, or the first 10.

    A file gets everything; the terminal gets a look at it. Ten rows is enough
    to see the shape of a column and short enough not to bury the header.
    """
    if has_output:
        return None                       # everything goes to the file
    if head:
        return slice(0, min(head, count))
    if tail:
        return slice(max(0, count - tail), count)
    return slice(0, min(10, count))
