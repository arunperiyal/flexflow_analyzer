"""/api/export — the plot workspace rendered via matplotlib at 300 dpi.

Phase 3 polish. No shared `plot_utils.save_figure()` exists to reuse (see
src/utils/plot_utils.py) -- each CLI call site builds its own Figure and
calls `fig.savefig(path, dpi=300, bbox_inches='tight')` directly
(src/commands/visualization/plot_impl/command.py and compare_impl/command.py).
This one deliberately does NOT use bbox_inches='tight': every panel here is
placed by an explicit, user-typed inches rect (Layout -> Panes), and cropping
to content would silently resize the figure away from the canvas size those
rects were positioned against.

The workspace lives in the browser (§5 of the plan), so the request carries
the panels/traces to render rather than the server holding any of it.
"""

import io

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from flask import Blueprint, current_app, jsonify, request, send_file

from ..services import registry
from ..services.columns import column_map as build_column_map
from ..services.loader import loader

bp = Blueprint('export', __name__, url_prefix='/api/export')

# Plotly's line.dash / marker.symbol names, mapped to matplotlib's own
# (unmapped values are left as matplotlib defaults: solid line, no marker).
_LINESTYLES = {'dash': '--', 'dot': ':', 'dashdot': '-.'}
_MARKERS = {'circle': 'o', 'square': 's', 'diamond': 'D', 'cross': '+', 'x': 'x', 'triangle-up': '^'}


def _matplotlib_font(css_family):
    """The first name in a CSS font-family stack (e.g. the style sidebar's
    '"Times New Roman", Times, serif'), unquoted -- matplotlib's
    rcParams['font.family'] takes a bare name, not CSS list syntax."""
    if not css_family:
        return None
    first = css_family.split(',')[0].strip().strip('"').strip("'")
    return first or None


def _pane_rect(panel, layout):
    """A panel's own pane (x, y, w, h -- inches, from Layout -> Panes), or
    the canvas-filling default when it hasn't been placed yet. Python
    mirror of plot.js's PlotArea.paneRect."""
    p = panel.get('pane')
    if isinstance(p, dict) and all(isinstance(p.get(k), (int, float)) for k in ('x', 'y', 'w', 'h')):
        return p
    return {'x': 0, 'y': 0, 'w': layout.get('width') or 6.5, 'h': layout.get('height') or 4.5}


def _pane_axes_rect(pane, width_in, height_in):
    """A pane's inches rect -> a matplotlib add_axes rect (figure-fraction
    [left, bottom, width, height], y counting up from the bottom). Clamped
    the same way plot.js's paneDomain is -- a pane typed past the canvas
    edge, or with zero/negative size, still renders instead of raising."""
    left = min(max(pane['x'] / width_in, 0), 1)
    right = min(max((pane['x'] + pane['w']) / width_in, 0), 1)
    bottom = min(max(1 - (pane['y'] + pane['h']) / height_in, 0), 1)
    top = min(max(1 - pane['y'] / height_in, 0), 1)
    if right <= left:
        right = min(1, left + 0.01)
    if top <= bottom:
        top = min(1, bottom + 0.01)
    return [left, bottom, right - left, top - bottom]


def _hide_ticks(ax, physical_axis):
    """Hide both the tick marks and their numbers on one physical
    matplotlib axis ('x' or 'y') -- leaves the spine and any axis title
    alone, matching plot.js's showticklabels + ticks:'' pairing."""
    if physical_axis == 'x':
        ax.tick_params(axis='x', bottom=False, top=False, labelbottom=False, labeltop=False)
    else:
        ax.tick_params(axis='y', left=False, right=False, labelleft=False, labelright=False)


def _plot_kwargs(trace, style):
    kwargs = {'linewidth': 1.0, 'linestyle': _LINESTYLES.get(trace.get('lineStyle'), '-')}
    marker = trace.get('marker')
    if marker and marker != 'none':
        kwargs['marker'] = _MARKERS.get(marker, 'o')
        kwargs['markersize'] = style.get('markerSize') or 4
        if style.get('markerStep', 0) > 1:
            kwargs['markevery'] = int(style['markerStep'])
    return kwargs


@bp.post('')
def export_png():
    root = current_app.config['WORKSPACE_ROOT']
    data = request.get_json(silent=True) or {}
    panels = data.get('panels') or []
    style = data.get('style') or {}
    layout = data.get('layout') or {}

    if not panels:
        return jsonify({'error': 'no panels to export'}), 400

    width_in = layout.get('width') or 6.5
    height_in = layout.get('height') or 4.5
    figsize = (width_in, height_in)

    # rc_context scopes the font override to this figure, rather than
    # mutating matplotlib's global rcParams for every concurrent request.
    font_name = _matplotlib_font(style.get('fontFamily'))
    with plt.rc_context({'font.family': font_name} if font_name else {}):
        fig = plt.figure(figsize=figsize)
        # Each panel gets its own freely positioned axes -- add_axes takes
        # a figure-fraction rect directly, no GridSpec/shared-track notion
        # needed since panes are independent (mirrors plot.js's paneDomain).
        for panel in panels:
            pane = _pane_rect(panel, layout)
            ax = fig.add_axes(_pane_axes_rect(pane, width_in, height_in))
            pstyle = panel.get('style') or {}

            if panel.get('kind') == 'spatial':
                # Not yet supported: a spatial trace has no single `row`
                # (get_node_displacements(row) is the time-domain shape this
                # export follows), so it needs its own /spatial-backed
                # reduction here rather than being force-fit into the same
                # code path.
                ax.text(0.5, 0.5, 'spatial panels are not yet exported',
                       ha='center', va='center', fontsize=8, color='#94a3b8', transform=ax.transAxes)
                ax.set_title(panel.get('title') or '', fontsize=9)
                ax.tick_params(labelsize=7)
                continue

            # Swap X/Y rotates the panel 90 degrees: pstyle's x*/y* fields
            # always describe the same logical quantity (time on X, the
            # plotted value on Y) regardless of swap -- swap only decides
            # which physical matplotlib axis (ax.xaxis vs ax.yaxis) each
            # one lands on, mirroring plot.js's logicalX/logicalY split.
            swap = bool(pstyle.get('swapAxes'))

            plotted = 0
            for trace in panel.get('traces') or []:
                values, times = _trace_values(root, trace)
                if values is None:
                    continue
                first, second = (values, times) if swap else (times, values)
                ax.plot(first, second, color=trace.get('color'),
                        label=f"{trace.get('case')} r{trace.get('row')} {trace.get('col')}",
                        **_plot_kwargs(trace, style))
                plotted += 1
            ax.set_title(panel.get('title') or '', fontsize=style.get('labelFontSize') or 9)
            ax.tick_params(labelsize=style.get('tickFontSize') or 7,
                           direction='in' if style.get('ticksInside') else 'out')
            ax.grid(style.get('showGrid', True))
            # A static PNG has no colored panel-tree to cross-reference
            # trace colors against (unlike the browser view), so unlike
            # there, a legend is shown by default here.
            if plotted and style.get('showLegend', True):
                ax.legend(fontsize=style.get('legendFontSize') or 6, loc='upper right')

            x_axis, y_axis = (ax.yaxis, ax.xaxis) if swap else (ax.xaxis, ax.yaxis)
            set_xlim, set_ylim = (ax.set_ylim, ax.set_xlim) if swap else (ax.set_xlim, ax.set_ylim)
            set_xlabel, set_ylabel = (ax.set_ylabel, ax.set_xlabel) if swap else (ax.set_xlabel, ax.set_ylabel)
            x_tick_axis, y_tick_axis = ('y', 'x') if swap else ('x', 'y')

            if pstyle.get('xlim'):
                set_xlim(pstyle['xlim'])
            if pstyle.get('ylim'):
                set_ylim(pstyle['ylim'])
            if pstyle.get('xtick', 0) > 0:
                x_axis.set_major_locator(MultipleLocator(pstyle['xtick']))
            if pstyle.get('ytick', 0) > 0:
                y_axis.set_major_locator(MultipleLocator(pstyle['ytick']))
            if pstyle.get('xtickangle') is not None:
                ax.tick_params(axis=x_tick_axis, labelrotation=pstyle['xtickangle'])
            if pstyle.get('ytickangle') is not None:
                ax.tick_params(axis=y_tick_axis, labelrotation=pstyle['ytickangle'])

            # Each panel's tick marks/numbers and axis title are shown or
            # hidden per-panel (Style sidebar's Panel section), not
            # inferred from grid position.
            if pstyle.get('showXTicks') is False:
                _hide_ticks(ax, x_tick_axis)
            if pstyle.get('showYTicks') is False:
                _hide_ticks(ax, y_tick_axis)

            if pstyle.get('showXLabel') is not False:
                set_xlabel(pstyle.get('xlabel') or 'time [s]', fontsize=style.get('labelFontSize') or 8)
            if pstyle.get('showYLabel') is not False and pstyle.get('ylabel'):
                set_ylabel(pstyle['ylabel'], fontsize=style.get('labelFontSize') or 9)

        if style.get('title'):
            fig.suptitle(style['title'], fontsize=(style.get('labelFontSize') or 9) + 2)
        # No tight_layout()/bbox_inches='tight' -- both would resize or
        # recrop the figure away from the exact (width_in, height_in)
        # canvas the panes were positioned against, which is the whole
        # point of typing an explicit rect per panel in Layout -> Panes.

        buf = io.BytesIO()
        fig.savefig(buf, dpi=300, format='png')
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
