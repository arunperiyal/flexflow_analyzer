"""/api/cases* — the registry (list, browse, scan, add, delete) and per-case metadata."""

from pathlib import Path

import numpy as np
from flask import Blueprint, current_app, jsonify, request

from src.core.simflow_config import SimflowConfig

from ..services import registry
from ..services.loader import loader

bp = Blueprint('cases', __name__, url_prefix='/api/cases')


@bp.get('')
def list_cases():
    root = current_app.config['WORKSPACE_ROOT']
    return jsonify(registry.list_cases(root))


@bp.post('/scan')
def scan():
    data = request.get_json(silent=True) or {}
    root = current_app.config['WORKSPACE_ROOT']
    scan_dir = Path(data.get('dir') or root).expanduser().resolve()
    if not scan_dir.is_dir():
        current_app.logbuf.write(f"scan: not a directory: {scan_dir}")
        return jsonify({'error': f'not a directory: {scan_dir}'}), 400

    candidates = registry.scan(scan_dir)
    current_app.logbuf.write(f"scanned {scan_dir}: {len(candidates)} candidate(s)")
    return jsonify({'candidates': candidates})


@bp.get('/browse')
def browse():
    """Backs Case -> Add's directory browser: the subdirectories of ?dir
    (default the workspace root), so the dialog can be clicked through
    (and its breadcrumbs clicked back up) instead of requiring an exact
    path typed in from memory."""
    root = current_app.config['WORKSPACE_ROOT']
    raw = request.args.get('dir') or str(root)
    try:
        target = Path(raw).expanduser().resolve()
    except OSError:
        return jsonify({'error': f'not a directory: {raw}'}), 400
    if not target.is_dir():
        return jsonify({'error': f'not a directory: {target}'}), 400

    return jsonify(registry.browse(target))


@bp.post('')
def add():
    data = request.get_json(silent=True) or {}
    root = current_app.config['WORKSPACE_ROOT']
    scan_dir = Path(data.get('dir') or root).expanduser().resolve()
    exclude = set(data.get('exclude') or [])
    if not scan_dir.is_dir():
        current_app.logbuf.write(f"case add: not a directory: {scan_dir}")
        return jsonify({'error': f'not a directory: {scan_dir}'}), 400

    with current_app.logbuf.capture():
        print(f"case add {scan_dir}")
        cases = registry.add_cases(root, scan_dir, exclude)
        names = ', '.join(c['name'] for c in cases) or '(none)'
        print(f"registered {names}")

    return jsonify(cases)


@bp.delete('/<name>')
def delete(name):
    root = current_app.config['WORKSPACE_ROOT']
    cases = registry.delete_case(root, name)
    current_app.logbuf.write(f"removed {name} from the registry")
    return jsonify(cases)


@bp.get('/<name>/meta')
def meta(name):
    root = current_app.config['WORKSPACE_ROOT']
    case_dir = registry.case_path(root, name)
    if case_dir is None:
        return jsonify({'error': f'no such case: {name}'}), 404

    try:
        series_meta = loader.meta(case_dir)
    except FileNotFoundError as exc:
        current_app.logbuf.write(f"{name}: {exc}")
        return jsonify({'error': str(exc)}), 404

    try:
        problem = SimflowConfig.find(case_dir).problem
    except Exception:
        problem = None

    times = series_meta.times
    dt = float(np.mean(np.diff(times))) if len(times) > 1 else None
    groups = [
        {
            'othId': g,
            'variables': sorted(series_meta.variables_of(g)),
            'columns': series_meta.column_names(g),
            'nodes': series_meta.nodes_of(g),
        }
        for g in series_meta.groups
    ]

    return jsonify({
        'problem': problem,
        'dt': dt,
        'groups': groups,
        'times': {
            'n': len(times),
            't_min': float(times.min()) if len(times) else None,
            't_max': float(times.max()) if len(times) else None,
        },
    })
