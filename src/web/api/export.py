"""/api/export — the plot workspace rendered via matplotlib at 300 dpi.

Phase 3 polish. No shared `plot_utils.save_figure()` exists to reuse (see
src/utils/plot_utils.py) -- each CLI call site builds its own Figure and
calls `fig.savefig(path, dpi=300, bbox_inches='tight')` directly
(src/commands/visualization/plot_impl/command.py and compare_impl/command.py);
this follows the same convention rather than inventing a different one.

The workspace lives in the browser (§5 of the plan), so the request carries
the panels/traces to render rather than the server holding any of it.
"""

import io

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Blueprint, current_app, jsonify, request, send_file

from ..services import registry
from ..services.columns import column_map as build_column_map
from ..services.loader import loader

bp = Blueprint('export', __name__, url_prefix='/api/export')


@bp.post('')
def export_png():
    root = current_app.config['WORKSPACE_ROOT']
    data = request.get_json(silent=True) or {}
    panels = data.get('panels') or []
    link_x = bool(data.get('linkX'))

    if not panels:
        return jsonify({'error': 'no panels to export'}), 400

    fig, axes = plt.subplots(len(panels), 1, figsize=(9, 2.6 * len(panels)),
                             sharex=link_x, squeeze=False)

    for ax, panel in zip(axes[:, 0], panels):
        plotted = 0
        for trace in panel.get('traces') or []:
            values, times = _trace_values(root, trace)
            if values is None:
                continue
            ax.plot(times, values, linewidth=1.0, color=trace.get('color'),
                    label=f"{trace.get('case')} r{trace.get('row')} {trace.get('col')}")
            plotted += 1
        ax.set_title(panel.get('title') or '', fontsize=9)
        ax.tick_params(labelsize=7)
        if plotted:
            ax.legend(fontsize=6, loc='upper right')

    axes[-1, 0].set_xlabel('time [s]', fontsize=8)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, dpi=300, bbox_inches='tight', format='png')
    plt.close(fig)
    buf.seek(0)

    current_app.logbuf.write(f"export: {len(panels)} panel(s) -> flexflow_plot.png (300 dpi)")
    return send_file(buf, mimetype='image/png', as_attachment=True,
                     download_name='flexflow_plot.png')


def _trace_values(root, trace):
    """(values, times) for one trace, or (None, None) if it cannot be read."""
    case_dir = registry.case_path(root, trace.get('case') or '')
    if case_dir is None:
        return None, None
    try:
        meta = loader.meta(case_dir)
        group = trace.get('group')
        cmap = build_column_map(meta, group)
        var_name, comp = cmap[trace.get('col')]
        meta, arrays = loader.load(case_dir, [var_name], group=group)
        row = trace.get('row')
        return arrays[var_name][:, row, comp], meta.times
    except (FileNotFoundError, KeyError, IndexError, TypeError):
        return None, None
