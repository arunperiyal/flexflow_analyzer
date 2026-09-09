"""/api/cases/<name>/field -- PLT field-data metadata for the Field menu.

Reads <case>/binary/*.plt via src/plt/fxplt.py (pure numpy, no Tecplot
license needed -- see that module's own header note). `field/steps` and
`field/info` are the web equivalents of `field list`'s step discovery and
`field info` (src/commands/field/info_impl/command.py), same sections minus
terminal color codes, as JSON.
"""

import os
import re
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from ...commands.field.locate import find_plt, list_steps, problem_name
from ...plt.convert import audit
from ...plt.fxplt import ZTYPE_VTK, PltFile
from ..services import registry

bp = Blueprint('field', __name__, url_prefix='/api/cases')

# ztype -> nodes per element, matching info_impl/command.py's own table.
_NODES_PER_ELEM = {1: 2, 2: 3, 3: 4, 4: 4, 5: 8}
_STEP_RE = re.compile(r'\.(\d+)\.plt$')


def _step_of(path):
    m = _STEP_RE.search(path.name)
    return int(m.group(1)) if m else None


def _binary_dir_or_error(root, name):
    """(case_dir, binary_dir, None) or (None, None, (response, status))."""
    case_dir = registry.case_path(root, name)
    if case_dir is None:
        return None, None, (jsonify({'error': f'no such case: {name}'}), 404)
    binary_dir = Path(case_dir) / 'binary'
    if not binary_dir.is_dir():
        return None, None, (jsonify({'error': f'no binary/ directory in this case'}), 404)
    return case_dir, binary_dir, None


@bp.get('/<name>/field/steps')
def field_steps(name):
    root = current_app.config['WORKSPACE_ROOT']
    case_dir, binary_dir, err = _binary_dir_or_error(root, name)
    if err:
        return err
    problem = problem_name(case_dir)
    return jsonify({'case': name, 'steps': list_steps(binary_dir, problem)})


@bp.get('/<name>/field/info')
def field_info(name):
    root = current_app.config['WORKSPACE_ROOT']
    case_dir, binary_dir, err = _binary_dir_or_error(root, name)
    if err:
        return err
    problem = problem_name(case_dir)

    all_plt = sorted(binary_dir.glob('*.plt'))
    if not all_plt:
        return jsonify({'error': f'no PLT files found in {binary_dir}'}), 404

    timestep = request.args.get('timestep', type=int)
    plt_path = find_plt(binary_dir, problem, timestep)
    if plt_path is None:
        return jsonify({'error': f'timestep {timestep} not found in {binary_dir}'}), 404

    try:
        plt = PltFile(str(plt_path))
    except Exception as exc:
        return jsonify({'error': f'could not parse {plt_path.name}: {exc}'}), 400

    basic = {
        'file': plt_path.name,
        'path': str(plt_path),
        'timestep': _step_of(plt_path),
        'size_mb': os.path.getsize(plt_path) / 1e6,
        'problem': problem,
        'nvars': len(plt.vars),
        'nzones': len(plt.zones),
        'plt_count': len(all_plt),
    }

    zones = []
    for zi, z in enumerate(plt.zones):
        try:
            owners = plt.shared_from(zi)
        except Exception:
            owners = []
        zones.append({
            'index': zi, 'name': z['name'],
            'type': ZTYPE_VTK.get(z['ztype'], f"type{z['ztype']}"),
            'nodes_per_elem': _NODES_PER_ELEM.get(z['ztype'], 8),
            'npts': z['npts'], 'nelem': z['nelem'],
            'shared_from': [plt.zones[j]['name'] for j in owners],
        })

    checks = {}
    if problem:
        pat = re.compile(rf'^{re.escape(problem)}\.\d+\.plt$')
        bad = [f.name for f in all_plt if not pat.match(f.name)]
        checks['naming_ok'] = not bad
        checks['naming_bad_files'] = bad
    else:
        checks['naming_ok'] = None
        checks['naming_bad_files'] = []

    zi = plt.first_volume_zone()
    a = audit(plt, zi)
    checks.update({
        'zone_name': a['zone_name'], 'cell': a['cell'], 'npe': a['npe'],
        'nelem': a['nelem'], 'npts': a['npts'], 'truncated': a['truncated'],
        'short_by_mb': a['short_by'] / 1e6 if a['truncated'] else 0.0,
        # A FETETRAHEDRON (4-node) volume zone almost always means an 8-node
        # brick mesh mislabeled by simflow.config's nen setting.
        'tetrahedron_warning': a['ztype'] == 4,
    })

    stats = None
    stats_error = None
    try:
        mm = plt.minmax(plt.first_volume_zone())
        stats = [{'variable': v, 'min': rng[0] if rng else None,
                  'max': rng[1] if rng else None, 'shared': rng is None}
                 for v, rng in mm.items()]
    except Exception as exc:
        stats_error = str(exc)

    return jsonify({
        'case': name, 'basic': basic, 'variables': list(plt.vars),
        'zones': zones, 'checks': checks, 'stats': stats, 'stats_error': stats_error,
    })
