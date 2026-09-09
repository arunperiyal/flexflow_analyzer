"""/api/cases/<name>/data/info -- case-level summary of othd/oisd time-history
data: file counts, groups, node counts, timestep/tsId span, PLT alignment,
and the variable table. The web equivalent of `data show`
(src/commands/data/show_impl/command.py), built on this app's own cached
loader.meta() instead of re-scanning, and the CLI's pure naming helpers
(src/commands/data/shared.py) instead of re-deriving short names.
"""

from flask import Blueprint, current_app, jsonify, request

from ...commands.data.shared import alias_of, out_freq, short_names
from ..services import registry
from ..services.columns import column_map as build_column_map
from ..services.data_stats import FUNCS, LOCATORS, locate, zeroloc
from ..services.loader import loader

bp = Blueprint('data', __name__, url_prefix='/api/cases')

_KINDS = ('othd', 'oisd')


def _describe_kind(case_dir, kind):
    """One kind's summary, or None if this case has no <kind>_files/."""
    try:
        meta = loader.meta(case_dir, kind=kind)
    except FileNotFoundError:
        return None

    freq = out_freq(case_dir)
    plt_alignment = None
    if freq:
        aligned = [int(t) for t in meta.tsids.tolist() if t % freq == 0]
        if aligned:
            plt_alignment = {'freq': freq, 'min': min(aligned), 'max': max(aligned),
                             'count': len(aligned)}

    groups = []
    for group in meta.groups:
        variables = meta.variables_of(group)
        shorts = short_names(variables)
        var_rows = [{'name': name, 'ncomp': info.ncomp, 'columns': info.columns,
                     'short': alias_of(name, info, shorts)}
                   for name, info in sorted(variables.items())]
        groups.append({'group': group, 'nodes': meta.nodes_of(group), 'variables': var_rows})

    return {
        'kind': kind,
        'files': len(meta.files),
        'group_label': meta.group_label,
        'groups': groups,
        'timesteps': len(meta.times),
        'time_min': float(meta.times.min()),
        'time_max': float(meta.times.max()),
        'tsid_min': int(meta.tsids.min()),
        'tsid_max': int(meta.tsids.max()),
        'plt_alignment': plt_alignment,
    }


@bp.get('/<name>/data/info')
def data_info(name):
    root = current_app.config['WORKSPACE_ROOT']
    case_dir = registry.case_path(root, name)
    if case_dir is None:
        return jsonify({'error': f'no such case: {name}'}), 404

    kind_param = request.args.get('kind', 'both')
    if kind_param not in (*_KINDS, 'both'):
        return jsonify({'error': f"kind must be 'othd', 'oisd' or 'both', got '{kind_param}'"}), 400
    kinds = _KINDS if kind_param == 'both' else (kind_param,)

    result = {kind: described for kind in kinds
             if (described := _describe_kind(case_dir, kind)) is not None}
    if not result:
        asked = ' or '.join(f'{k}_files/' for k in kinds)
        return jsonify({'error': f'no {asked} data found under {case_dir}'}), 404

    # The two are written by the same run, so a disagreement in their step
    # count means one of them stopped early -- worth surfacing rather than
    # leaving it to be noticed later when the two dashboards don't line up
    # (mirrors _run_preview's own cross-check in show_impl/command.py).
    warning = None
    if len(result) == 2 and result['othd']['timesteps'] != result['oisd']['timesteps']:
        warning = (f"othd has {result['othd']['timesteps']} timesteps but oisd has "
                  f"{result['oisd']['timesteps']}; one of them stopped early")

    return jsonify({'case': name, **result, 'warning': warning})


def _tsid_window_mask(tsids, t1, t2):
    """Boolean mask selecting tsId in [t1, t2], each end open (None -> whole
    range). tsId rather than physical time, matching data stats --t1/--t2
    (shared.step_mask's own docstring) -- so the window lines up with the
    same steps `field extract`/`field render` would take, and a locator's
    answer is already in the units of a PLT filename."""
    lo = int(tsids.min()) if t1 is None else t1
    hi = int(tsids.max()) if t2 is None else t2
    if lo > hi:
        lo, hi = hi, lo
    return (tsids >= lo) & (tsids <= hi)


@bp.get('/<name>/data/stats')
def data_stats(name):
    root = current_app.config['WORKSPACE_ROOT']
    case_dir = registry.case_path(root, name)
    if case_dir is None:
        return jsonify({'error': f'no such case: {name}'}), 404

    columns = [c for c in request.args.get('columns', '').split(',') if c]
    if not columns:
        return jsonify({'error': 'columns is required'}), 400

    funcs = [f for f in request.args.get('funcs', '').split(',') if f]
    if not funcs:
        return jsonify({'error': 'funcs is required'}), 400
    known = set(FUNCS) | set(LOCATORS)
    unknown_funcs = [f for f in funcs if f not in known]
    if unknown_funcs:
        return jsonify({'error': f"unknown func(s): {', '.join(unknown_funcs)}. "
                                  f"available: {', '.join(sorted(known))}"}), 400

    kind = request.args.get('kind', 'othd')
    if kind not in _KINDS:
        return jsonify({'error': f"kind must be 'othd' or 'oisd', got '{kind}'"}), 400

    try:
        series_meta = loader.meta(case_dir, kind=kind)
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404

    group = request.args.get('group', type=int)
    group = series_meta.default_group if group is None else group
    if group not in series_meta.by_group:
        return jsonify({'error': f'no group {group}. present: {series_meta.groups}'}), 400

    column_map = build_column_map(series_meta, group)
    unknown_cols = [c for c in columns if c not in column_map]
    if unknown_cols:
        return jsonify({'error': f"unknown column(s): {', '.join(unknown_cols)}. "
                                  f"available: {', '.join(sorted(column_map))}"}), 400

    needed_vars = sorted({column_map[c][0] for c in columns})
    try:
        meta, arrays = loader.load(case_dir, needed_vars, group=group, kind=kind)
    except KeyError as exc:
        return jsonify({'error': str(exc)}), 400

    nnodes = meta.nodes_of(group)
    node = request.args.get('node', default=0, type=int)
    if node < 0 or node >= nnodes:
        return jsonify({'error': f'node out of range (0..{nnodes - 1}): {node}'}), 400

    t1 = request.args.get('t1', type=int)
    t2 = request.args.get('t2', type=int)
    mask = _tsid_window_mask(meta.tsids, t1, t2)
    if not mask.any():
        return jsonify({'error': 'no timesteps in that window'}), 400

    tsids = meta.tsids[mask]
    times = meta.times[mask]
    freq = out_freq(case_dir)

    value_funcs = [f for f in funcs if f in FUNCS]
    result = {'case': name, 'group': group, 'kind': kind, 'node': node,
             'tsid_min': int(tsids.min()), 'tsid_max': int(tsids.max()),
             'steps': int(mask.sum()), 'freq': freq, 'values': []}
    for direction in ('max', 'min'):
        if f'{direction}loc' in funcs:
            result[f'{direction}loc'] = []
    if 'zeroloc' in funcs:
        result['zeroloc'] = []

    for col in columns:
        var_name, comp = column_map[col]
        series_values = arrays[var_name][mask, node, comp]

        if value_funcs:
            row = {'column': col}
            for f in value_funcs:
                row[f] = FUNCS[f](series_values)
            result['values'].append(row)

        for direction in ('max', 'min'):
            key = f'{direction}loc'
            if key not in funcs:
                continue
            found = locate(series_values, tsids, times, freq, direction)
            result[key].append({'column': col, **found})

        if 'zeroloc' in funcs:
            for direction in ('descending', 'ascending'):
                found = zeroloc(series_values, tsids, times, freq, direction)
                result['zeroloc'].append({'column': col, **found})

    return jsonify(result)
