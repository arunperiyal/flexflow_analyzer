"""/api/cases/<name>/fft — frequency spectra for the plot workspace.

Same shape as /history (batched over rows and columns for one case/group/
kind), since the input is exactly the same time series -- this just
transforms it before responding, via services/fft.py, rather than handing
back the raw values. An optional t1/t2 window (see /spatial's stat mode)
restricts the spectrum to a stretch of the signal -- comparing an early
transient against a later steady state, say -- rather than the whole run.
"""

from flask import Blueprint, current_app, jsonify, request

from ..services import registry
from ..services.columns import column_map as build_column_map
from ..services.fft import compute_fft
from ..services.loader import loader
from ..services.spatial import window_mask

bp = Blueprint('fft', __name__, url_prefix='/api/cases')

MAX_ROWS = 32


@bp.get('/<name>/fft')
def fft(name):
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

    kind = request.args.get('kind', 'othd')
    if kind not in ('othd', 'oisd'):
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

    unknown = [c for c in columns if c not in column_map]
    if unknown:
        return jsonify({'error': f"unknown column(s): {', '.join(unknown)}. "
                                  f"available: {', '.join(sorted(column_map))}"}), 400

    needed_vars = sorted({column_map[c][0] for c in columns})
    try:
        meta, arrays = loader.load(case_dir, needed_vars, group=group, kind=kind)
    except KeyError as exc:
        return jsonify({'error': str(exc)}), 400

    nnodes = meta.nodes_of(group)
    bad_rows = [r for r in rows if r < 0 or r >= nnodes]
    if bad_rows:
        return jsonify({'error': f"row(s) out of range (0..{nnodes - 1}): {bad_rows}"}), 400

    # An optional time window, same shape as /spatial's stat mode: both ends
    # open, None -> the whole series. Windowing before compute_fft (not
    # inside it) keeps compute_fft itself about "one already-chosen stretch
    # of samples", not about picking which ones.
    t1 = request.args.get('t1', type=float)
    t2 = request.args.get('t2', type=float)
    mask = window_mask(meta.times, t1, t2)
    if not mask.any():
        return jsonify({'error': 'no timesteps in that window'}), 400
    windowed_times = meta.times[mask]

    try:
        # Every (row, column) in one case/group shares the same times, so
        # the frequency axis is computed once -- only the amplitude differs.
        freqs = None
        series = []
        for col in columns:
            var_name, comp = column_map[col]
            arr = arrays[var_name]              # (nsteps, nnodes, ncomp)
            for row in rows:
                f, amplitude = compute_fft(windowed_times, arr[mask, row, comp])
                freqs = f
                series.append({'row': row, 'column': col, 'amplitude': amplitude.tolist()})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    return jsonify({'case': name, 'group': group, 'frequencies': freqs.tolist(), 'series': series,
                    't1': float(windowed_times[0]), 't2': float(windowed_times[-1])})
