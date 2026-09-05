"""/api/cases/<name>/spatial — per-node snapshots and time-window statistics.

x is the picker's own spatial coordinate, already known to the browser from
the map/view it loaded (project.py's projection); this endpoint only
returns y -- one value per (row, column), either at a single time
(mode=snapshot) or reduced over a time window (mode=stat).
"""

from flask import Blueprint, current_app, jsonify, request

from ..services import registry
from ..services.columns import column_map as build_column_map
from ..services.loader import loader
from ..services.spatial import STATS, nearest_time_index, window_mask

bp = Blueprint('spatial', __name__, url_prefix='/api/cases')

MAX_ROWS = 256


@bp.get('/<name>/spatial')
def spatial(name):
    root = current_app.config['WORKSPACE_ROOT']
    case_dir = registry.case_path(root, name)
    if case_dir is None:
        return jsonify({'error': f'no such case: {name}'}), 404

    columns = [c for c in request.args.get('columns', '').split(',') if c]
    rows_param = request.args.get('rows', '')
    try:
        rows = [int(r) for r in rows_param.split(',') if r != '']
    except ValueError:
        return jsonify({'error': 'rows must be comma-separated integers'}), 400

    if not columns or not rows:
        return jsonify({'error': 'columns and rows are both required'}), 400
    if len(rows) > MAX_ROWS:
        return jsonify({'error': f'at most {MAX_ROWS} rows per request'}), 400

    mode = request.args.get('mode', 'snapshot')
    if mode not in ('snapshot', 'stat'):
        return jsonify({'error': "mode must be 'snapshot' or 'stat'"}), 400

    try:
        series_meta = loader.meta(case_dir)
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404

    group = request.args.get('group', type=int)
    group = series_meta.default_group if group is None else group
    if group not in series_meta.by_group:
        return jsonify({'error': f'no group {group}. present: {series_meta.groups}'}), 400

    column_map = build_column_map(series_meta, group)
    unknown = [c for c in columns if c not in column_map]
    if unknown:
        return jsonify({'error': f"unknown column(s): {', '.join(unknown)}. "
                                  f"available: {', '.join(sorted(column_map))}"}), 400

    needed_vars = sorted({column_map[c][0] for c in columns})
    try:
        meta, arrays = loader.load(case_dir, needed_vars, group=group)
    except KeyError as exc:
        return jsonify({'error': str(exc)}), 400

    nnodes = meta.nodes_of(group)
    bad_rows = [r for r in rows if r < 0 or r >= nnodes]
    if bad_rows:
        return jsonify({'error': f"row(s) out of range (0..{nnodes - 1}): {bad_rows}"}), 400

    times = meta.times

    if mode == 'snapshot':
        time_param = request.args.get('time', type=float)
        if time_param is None:
            return jsonify({'error': "mode=snapshot requires 'time'"}), 400
        t_idx = nearest_time_index(times, time_param)
        values = [
            {'row': row, 'column': col, 'value': float(arrays[column_map[col][0]][t_idx, row, column_map[col][1]])}
            for col in columns for row in rows
        ]
        return jsonify({'case': name, 'group': group, 'mode': 'snapshot',
                        'time': float(times[t_idx]), 'values': values})

    # mode == 'stat'
    stats_param = [s for s in request.args.get('stats', '').split(',') if s]
    if not stats_param:
        return jsonify({'error': 'mode=stat requires stats'}), 400
    unknown_stats = [s for s in stats_param if s not in STATS]
    if unknown_stats:
        return jsonify({'error': f"unknown stat(s): {', '.join(unknown_stats)}. "
                                  f"available: {', '.join(sorted(STATS))}"}), 400

    t1 = request.args.get('t1', type=float)
    t2 = request.args.get('t2', type=float)
    mask = window_mask(times, t1, t2)
    if not mask.any():
        return jsonify({'error': 'no timesteps in that window'}), 400

    values = []
    for col in columns:
        var_name, comp = column_map[col]
        arr = arrays[var_name]
        for row in rows:
            series = arr[mask, row, comp]
            for stat in stats_param:
                values.append({'row': row, 'column': col, 'stat': stat,
                               'value': STATS[stat](series)})

    windowed_times = times[mask]
    return jsonify({'case': name, 'group': group, 'mode': 'stat',
                    't1': float(windowed_times[0]), 't2': float(windowed_times[-1]),
                    'values': values})
