"""/api/cases/<name>/maps* — probe sets and their rows (§6–8 of the plan)."""

from pathlib import Path

import numpy as np
from flask import Blueprint, current_app, jsonify, request

from src.commands.case.out_impl.command import WriteError, write_case_maps
from src.core.domain import DomainConfig
from src.utils.logger import Logger

from ..services import registry
from ..services.frame import resolve_body, resolve_output
from ..services.jobs import jobs
from ..services.loader import loader
from ..services.mapfile import list_maps, parse_map, list_surface_maps, parse_surface_map
from ..services.project import Frame, project, views_for

bp = Blueprint('maps', __name__, url_prefix='/api/cases')


def _case_dir_or_404(root, name):
    case_dir = registry.case_path(root, name)
    if case_dir is None:
        return None, (jsonify({'error': f'no such case: {name}'}), 404)
    return case_dir, None


def _body_summary(body):
    return {'name': body.get('name'), 'type': body.get('type')} if body else None


def _map_summary(case_dir, path, domain):
    """One row of the maps list: the three cross-checks from §6–7."""
    parsed = parse_map(path)
    body = resolve_body(domain, parsed.block) if parsed.block else None
    output = resolve_output(domain, parsed.block) if parsed.block else None

    oth_id_ok = rows_match = None
    try:
        series_meta = loader.meta(case_dir)
        if parsed.oth_id is not None:
            oth_id_ok = parsed.oth_id in series_meta.groups
            if oth_id_ok:
                rows_match = series_meta.nodes_of(parsed.oth_id) == len(parsed.rows)
    except FileNotFoundError:
        pass

    nodes_ok = None
    if output and output.get('nodes') and parsed.provenance_file:
        nodes_ok = Path(output['nodes']).name == Path(parsed.provenance_file).name

    return {
        'file': path.name,
        'kind': 'node',
        'block': parsed.block,
        'probe': parsed.probe,
        'closed': parsed.closed,
        'oth_id': parsed.oth_id,
        'rows': len(parsed.rows),
        'has_node_col': parsed.has_node_col,
        'oth_id_ok': oth_id_ok,
        'rows_match': rows_match,
        'nodes_ok': nodes_ok,
        'body': _body_summary(body),
    }


def _surface_map_summary(case_dir, path):
    """One row of the maps list, for an outputSurface's oisd.*.map -- the
    surface-shaped counterpart to _map_summary. No `probe`/`rows_match`/
    `nodes_ok`: those describe a per-node map's row->node/coordinate
    correctness, which has no counterpart here (a surface map's rows are its
    mesh, not indexed oisd data)."""
    parsed = parse_surface_map(path)

    osg_id_ok = None
    try:
        surface_meta = loader.meta(case_dir, kind='oisd')
        if parsed.osg_id is not None:
            osg_id_ok = parsed.osg_id in surface_meta.groups
    except FileNotFoundError:
        pass

    return {
        'file': path.name,
        'kind': 'surface',
        'block': parsed.block,
        'element_group': parsed.element_group,
        'shape': parsed.shape,
        'osg_id': parsed.osg_id,
        'osg_id_ok': osg_id_ok,
        'nodes': len(parsed.nodes),
        'elements': len(parsed.elements),
    }


def _all_map_summaries(case_dir, domain):
    """Every map this case has, node and surface alike -- one list, one
    request, since Plot -> New's map picker treats them as one set of
    choices."""
    summaries = [_map_summary(case_dir, p, domain) for p in list_maps(case_dir)]
    summaries += [_surface_map_summary(case_dir, p) for p in list_surface_maps(case_dir)]
    return summaries


@bp.get('/<name>/maps')
def list_case_maps(name):
    root = current_app.config['WORKSPACE_ROOT']
    case_dir, err = _case_dir_or_404(root, name)
    if err:
        return err
    domain = DomainConfig.find(case_dir)
    return jsonify(_all_map_summaries(case_dir, domain))


def _get_surface_map(path):
    parsed = parse_surface_map(path)
    return jsonify({
        'header': {
            'kind': 'surface',
            'block': parsed.block,
            'element_group': parsed.element_group,
            'shape': parsed.shape,
            'osg_id': parsed.osg_id,
        },
        'views': [],
        # A synthetic single row, in the same shape a node map's `rows[0]`
        # takes -- an outputSurface has exactly one, the whole surface, so
        # there is nothing to pick.
        'rows': [{'row': 0, 'node': None}],
        'projection': None,
    })


@bp.get('/<name>/maps/<mapfile>')
def get_map(name, mapfile):
    root = current_app.config['WORKSPACE_ROOT']
    case_dir, err = _case_dir_or_404(root, name)
    if err:
        return err
    path = case_dir / mapfile
    if not path.is_file():
        return jsonify({'error': f'no such map: {mapfile}'}), 404

    if mapfile.startswith('oisd.'):
        return _get_surface_map(path)

    parsed = parse_map(path)
    domain = DomainConfig.find(case_dir)
    body = resolve_body(domain, parsed.block) if parsed.block else None
    frame = Frame.from_body(body)
    probe = parsed.probe or 'cloud'
    views = views_for(probe, frame)

    view_id = request.args.get('view') or (views[0]['id'] if views else None)
    projection = None
    if view_id and parsed.rows:
        points = np.array([[r['x'], r['y'], r['z']] for r in parsed.rows], dtype=float)
        projection = project(view_id, points, frame)
        projection['view'] = view_id

    return jsonify({
        'header': {
            'block': parsed.block, 'probe': parsed.probe, 'closed': parsed.closed,
            'oth_id': parsed.oth_id, 'has_node_col': parsed.has_node_col,
            'body': _body_summary(body),
        },
        'views': views,
        'rows': parsed.rows,
        'projection': projection,
    })


@bp.post('/<name>/maps')
def write_maps(name):
    """Run `case out --map` for this case -- the "Write map now" button."""
    root = current_app.config['WORKSPACE_ROOT']
    case_dir, err = _case_dir_or_404(root, name)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    targets = data.get('blocks') or [None]   # None -> every mappable block

    def run():
        logger = Logger(verbose=True)
        for block in targets:
            try:
                write_case_maps(case_dir, block, logger)
            except WriteError as exc:
                if not exc.skip:
                    raise
                continue

        domain = DomainConfig.find(case_dir)
        return _all_map_summaries(case_dir, domain)

    job_id = jobs.start(run)
    return jsonify({'job_id': job_id}), 202
