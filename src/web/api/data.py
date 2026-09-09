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
