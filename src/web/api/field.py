"""/api/cases/<name>/field -- PLT field-data metadata for the Field menu.

Reads <case>/binary/*.plt via src/plt/fxplt.py (pure numpy, no Tecplot
license needed -- see that module's own header note). `field/steps` and
`field/info` are the web equivalents of `field list`'s step discovery and
`field info` (src/commands/field/info_impl/command.py), same sections minus
terminal color codes, as JSON.
"""

import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

from flask import Blueprint, after_this_request, current_app, jsonify, request, send_file

from ...commands.field.locate import find_plt, list_steps, problem_name
from ...plt.convert import audit
from ...plt.fxplt import ZTYPE_VTK, PltFile
from ..services import registry
from ..services.field_extract import resolve_steps, run_probe_extract, write_mesh_vtu
from ..services.field_render import MODES as RENDER_MODES
from ..services.field_render import render_field, render_field_mesh
from ..services.jobs import jobs

bp = Blueprint('field', __name__, url_prefix='/api/cases')

MAX_EXTRACT_STEPS = 50

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


def _render_cache_dir(root, case_name):
    """Persistent, server-side storage for files added to a layout as `render`
    panels (Field -> Render) -- a .vtp mesh for the interactive viewer, or a
    PNG for the older snapshot path. Deliberately outside the case's own directory
    (often a read-only/shared scratch mount) and outside the OS temp dir a
    render job first writes into (not guaranteed to survive a reboot), so a
    saved panel keeps working across server restarts and browser reloads --
    unlike a job's own tempdir, which `services/jobs.py`'s in-memory
    JobRegistry stops being able to resolve after a restart anyway."""
    return Path(root) / '.flexflow_web_renders' / case_name


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


@bp.post('/<name>/field/extract')
def field_extract(name):
    """Probe-point sampling, run as a background job (services/jobs.py --
    already used for map-writing) since it can touch several large PLT files.
    Poll the result at the existing GET /api/jobs/<id>."""
    root = current_app.config['WORKSPACE_ROOT']
    case_dir, binary_dir, err = _binary_dir_or_error(root, name)
    if err:
        return err
    problem = problem_name(case_dir)

    body = request.get_json(silent=True) or {}
    zone = body.get('zone')
    if not zone:
        return jsonify({'error': 'zone is required'}), 400
    columns = body.get('columns') or []
    if not columns:
        return jsonify({'error': 'columns is required'}), 400
    points_raw = body.get('points') or []
    if not points_raw:
        return jsonify({'error': 'at least one point is required'}), 400
    try:
        points = [[float(p['x']), float(p['y']), float(p['z'])] for p in points_raw]
    except (KeyError, TypeError, ValueError):
        return jsonify({'error': 'each point needs numeric x, y, z'}), 400

    steps = resolve_steps(binary_dir, problem, body.get('timestep'), body.get('t1'), body.get('t2'))
    if steps is None:
        return jsonify({'error': 'give a timestep, or both t1 and t2'}), 400
    if not steps:
        return jsonify({'error': 'no PLT files in that timestep range'}), 400
    if len(steps) > MAX_EXTRACT_STEPS:
        return jsonify({'error': f'at most {MAX_EXTRACT_STEPS} timesteps per request '
                                  f'({len(steps)} given)'}), 400

    interpolate = bool(body.get('interpolate'))

    def run():
        cols, rows, notes = run_probe_extract(binary_dir, problem, zone, columns, points, steps,
                                              interpolate=interpolate)
        return {'columns': cols, 'rows': rows, 'notes': notes}

    job_id = jobs.start(run)
    return jsonify({'job_id': job_id}), 202


@bp.get('/<name>/field/mesh.vtu')
def field_mesh(name):
    """Download one zone's mesh at one timestep, as a binary .vtu -- opens
    directly in ParaView. Every variable the zone carries, not a filtered
    subset (see write_mesh_vtu's own docstring)."""
    root = current_app.config['WORKSPACE_ROOT']
    case_dir, binary_dir, err = _binary_dir_or_error(root, name)
    if err:
        return err
    problem = problem_name(case_dir)

    zone = request.args.get('zone')
    if not zone:
        return jsonify({'error': 'zone is required'}), 400
    timestep = request.args.get('timestep', type=int)
    plt_path = find_plt(binary_dir, problem, timestep)
    if plt_path is None:
        msg = f'timestep {timestep} not found' if timestep is not None else 'no PLT files found'
        return jsonify({'error': msg}), 404

    fd, tmp_path = tempfile.mkstemp(suffix='.vtu')
    os.close(fd)
    try:
        write_mesh_vtu(plt_path, zone, tmp_path)
    except ValueError as exc:
        os.unlink(tmp_path)
        return jsonify({'error': str(exc)}), 400

    @after_this_request
    def _cleanup(response):
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return response

    download_name = f'{name}_{zone}_{_step_of(plt_path)}.vtu'
    return send_file(tmp_path, as_attachment=True, download_name=download_name,
                     mimetype='application/octet-stream')


def _check_color_range(rng):
    """None (unset -- render.py picks it from the data), or [min, max] with
    min < max. Anything else is a 400, matching render_impl/command.py's own
    _check_range/_check_config guard against a malformed color.range."""
    if rng is None:
        return None, None
    if not (isinstance(rng, (list, tuple)) and len(rng) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in rng)):
        return None, f'color range must be [min, max], got {rng!r}'
    if rng[0] >= rng[1]:
        return None, f'color range needs min below max, got {rng[0]} and {rng[1]}'
    return [float(rng[0]), float(rng[1])], None


def _parse_render_body(body):
    """Shared by field_render and field_render_mesh: mode/timestep/zone and
    the render.py-shaped `overrides` dict (color/contour/slice), plus the PNG
    gallery's `views` (unused by the mesh route, which has a live camera
    instead of fixed presets). Returns (mode, zone, timestep, overrides,
    view_names, error) -- error is None on success, else a (response,
    status) pair to return directly, matching _binary_dir_or_error's shape."""
    mode = body.get('mode')
    if mode not in RENDER_MODES:
        return None, None, None, None, None, (jsonify({'error': f"mode must be 'iso' or 'slice', got '{mode}'"}), 400)
    timestep = body.get('timestep')
    if timestep is None:
        return None, None, None, None, None, (jsonify({'error': 'timestep is required'}), 400)
    try:
        timestep = int(timestep)
    except (TypeError, ValueError):
        return None, None, None, None, None, (jsonify({'error': 'timestep must be an integer'}), 400)

    zone = body.get('zone') or None   # falsy/absent -> render.py's first volume zone
    view_names = body.get('views') or []

    color = body.get('color') or {}
    color_range, range_err = _check_color_range(color.get('range'))
    if range_err:
        return None, None, None, None, None, (jsonify({'error': range_err}), 400)

    overrides = {'color': {}}
    if color.get('variable'):
        overrides['color']['variable'] = color['variable']
    if color_range:
        overrides['color']['range'] = color_range

    if mode == 'iso':
        contour = body.get('contour') or {}
        overrides['contour'] = {}
        if contour.get('variable'):
            overrides['contour']['variable'] = contour['variable']
        if contour.get('isosurfaces'):
            overrides['contour']['isosurfaces'] = contour['isosurfaces']
    else:
        slice_cfg = body.get('slice') or {}
        overrides['slice'] = {}
        if slice_cfg.get('normal'):
            overrides['slice']['normal'] = slice_cfg['normal']
        if slice_cfg.get('origin'):
            overrides['slice']['origin'] = slice_cfg['origin']
        if slice_cfg.get('count'):
            overrides['slice']['count'] = slice_cfg['count']

    return mode, zone, timestep, overrides, view_names, None


@bp.post('/<name>/field/render')
def field_render(name):
    """Iso-surface or slice-plane PNG(s) for one timestep, run as a
    background job (services/jobs.py) since pyvista rendering takes real
    wall-clock time. Poll the result at the existing GET /api/jobs/<id>;
    each PNG in the result's `files` list becomes a layout panel by POSTing
    its filename to .../field/render/<job_id>/save (field_render_save)."""
    root = current_app.config['WORKSPACE_ROOT']
    case_dir, binary_dir, err = _binary_dir_or_error(root, name)
    if err:
        return err
    problem = problem_name(case_dir)

    body = request.get_json(silent=True) or {}
    mode, zone, timestep, overrides, view_names, err = _parse_render_body(body)
    if err:
        return err

    # A run always writes into a directory of its own -- never cleaned up
    # automatically in this v1 (matches an accepted, noted limitation: a
    # periodic sweep of old flexflow_render_* dirs is a follow-up, not part
    # of this pass).
    job_out_dir = tempfile.mkdtemp(prefix='flexflow_render_')

    def run():
        outs = render_field(binary_dir, problem, zone, mode, timestep, overrides,
                            view_names, job_out_dir)
        files = [str(Path(p).relative_to(job_out_dir)) for p in outs]
        return {'dir': job_out_dir, 'files': files}

    job_id = jobs.start(run)
    return jsonify({'job_id': job_id}), 202


@bp.post('/<name>/field/render-mesh')
def field_render_mesh(name):
    """The extracted iso-surface/slice geometry for one timestep, as a .vtp
    file, for the Field -> Render dialog's interactive 3-D viewer. Same
    background-job/poll shape as field_render, but no `views` (a live camera
    replaces fixed presets) and no GL context needed at all -- see
    services/field_render.py's render_field_mesh."""
    root = current_app.config['WORKSPACE_ROOT']
    case_dir, binary_dir, err = _binary_dir_or_error(root, name)
    if err:
        return err
    problem = problem_name(case_dir)

    body = request.get_json(silent=True) or {}
    mode, zone, timestep, overrides, _view_names, err = _parse_render_body(body)
    if err:
        return err

    job_out_dir = tempfile.mkdtemp(prefix='flexflow_render_')

    def run():
        mesh = render_field_mesh(binary_dir, problem, zone, mode, timestep, overrides, job_out_dir)
        return {'dir': job_out_dir, 'files': [mesh['file']],
                'variables': mesh['variables'], 'colorVar': mesh['colorVar']}

    job_id = jobs.start(run)
    return jsonify({'job_id': job_id}), 202


@bp.post('/<name>/field/render/<job_id>/save')
def field_render_save(name, job_id):
    """Copy one file from a completed render job's tempdir into this case's
    persistent render cache, for a Field -> Render panel to reference. Runs
    server-side (no HTTP hop through a "fetch the job's own file" route --
    there isn't one anymore, this is the only thing that ever read a job's
    output) so the job's in-memory registry only needs to be reachable once,
    right now, not every time the resulting panel is displayed later."""
    root = current_app.config['WORKSPACE_ROOT']
    if registry.case_path(root, name) is None:
        return jsonify({'error': f'no such case: {name}'}), 404

    job = jobs.get(job_id)
    if job is None or job.status != 'done' or not isinstance(job.result, dict):
        return jsonify({'error': 'no such completed render job'}), 404
    directory = job.result.get('dir')
    files = job.result.get('files') or []
    body = request.get_json(silent=True) or {}
    filename = body.get('filename')
    if not directory or filename not in files:
        return jsonify({'error': 'no such file in this render job'}), 404

    dest_dir = _render_cache_dir(root, name)
    dest_dir.mkdir(parents=True, exist_ok=True)
    token = f'{uuid.uuid4().hex}{Path(filename).suffix}'
    shutil.copyfile(Path(directory) / filename, dest_dir / token)

    return jsonify({'token': token, 'case': name})


@bp.get('/<name>/field/render-file/<token>')
def field_render_cached_file(name, token):
    """Serves a file saved by field_render_save -- a PNG (the old snapshot
    panel) or a .vtp mesh (the interactive viewer's meshToken, fetched
    client-side by meshviewer.js's vtkXMLPolyDataReader). Deliberately
    independent of services/jobs.py's in-memory JobRegistry: this must keep
    working after a server restart, unlike the job it was originally
    rendered by. Content-Type is left to Flask/send_file's own guess from
    the extension rather than hardcoded, since this now serves more than
    one file type."""
    root = current_app.config['WORKSPACE_ROOT']
    if registry.case_path(root, name) is None:
        return jsonify({'error': f'no such case: {name}'}), 404
    if '/' in token or '..' in token:
        return jsonify({'error': 'invalid token'}), 400

    path = _render_cache_dir(root, name) / token
    if not path.is_file():
        return jsonify({'error': 'no such saved render'}), 404
    return send_file(path)
