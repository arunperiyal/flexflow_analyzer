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
from matplotlib.gridspec import GridSpec
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


def _compute_slots(rows, columns, areas):
    """Python port of plot.js's computeSlots: every cell of the grid as
    non-overlapping rectangular slots -- `areas` (merged, span > 1x1) first,
    then every remaining cell as its own implicit 1x1 slot. An invalid area
    (out of bounds, or overlapping an earlier one) is dropped. Sorted
    row-major by top-left corner."""
    covered = set()
    slots = []
    for a in areas or []:
        row, col = a.get('row'), a.get('col')
        row_span, col_span = a.get('rowSpan') or 0, a.get('colSpan') or 0
        if row_span <= 0 or col_span <= 0:
            continue
        if row is None or col is None or row < 0 or col < 0 or row + row_span > rows or col + col_span > columns:
            continue
        cells = [(r, c) for r in range(row, row + row_span) for c in range(col, col + col_span)]
        if any(cell in covered for cell in cells):
            continue
        covered.update(cells)
        slots.append({'row': row, 'col': col, 'rowSpan': row_span, 'colSpan': col_span})
    for r in range(rows):
        for c in range(columns):
            if (r, c) not in covered:
                slots.append({'row': r, 'col': c, 'rowSpan': 1, 'colSpan': 1})
    slots.sort(key=lambda s: (s['row'], s['col']))
    return slots


def _resolve_panes(panels, layout):
    """Python port of plot.js's resolvePanes: honors valid, non-conflicting
    explicit panel['pane'] assignments (a slot's top-left cell), then falls
    back unassigned/conflicting panels to the next free slot in row-major
    order, growing rows (as new, unmerged 1x1 rows) as needed."""
    columns = max(1, int(layout.get('columns') or 1))
    rows = max(1, int(layout.get('rows') or 1))
    slots = _compute_slots(rows, columns, layout.get('areas'))
    by_key = {(s['row'], s['col']): s for s in slots}
    used = set()
    pane_of = {}

    for panel in panels:
        p = panel.get('pane')
        if p and isinstance(p.get('row'), int) and isinstance(p.get('col'), int):
            key = (p['row'], p['col'])
            slot = by_key.get(key)
            if slot and key not in used:
                used.add(key)
                pane_of[panel['id']] = slot

    free_slots = [s for s in slots if (s['row'], s['col']) not in used]
    free_idx = 0
    for panel in panels:
        if panel['id'] in pane_of:
            continue
        if free_idx >= len(free_slots):
            rows += 1
            for c in range(columns):
                free_slots.append({'row': rows - 1, 'col': c, 'rowSpan': 1, 'colSpan': 1})
        slot = free_slots[free_idx]
        free_idx += 1
        used.add((slot['row'], slot['col']))
        pane_of[panel['id']] = slot

    return rows, columns, pane_of


def _resolve_link_groups(panels, pane_of, link_groups):
    """Python port of plot.js's resolveLinkGroups: which x-axis-link group
    (if any) each panel belongs to, keyed by pane position. None means
    "auto" -- every non-spatial, non-swapped panel in one implicit group,
    same as the old blanket "Link x-axes" checkbox. Returns {panel id:
    group key}, with no entry at all for a panel in no group."""
    def eligible(panel):
        return panel.get('kind') != 'spatial' and not (panel.get('style') or {}).get('swapAxes')

    group_of = {}
    if link_groups is None:
        for panel in panels:
            if eligible(panel):
                group_of[panel['id']] = 'auto'
        return group_of

    for group_idx, pane_keys in enumerate(link_groups or []):
        key_set = {(p['row'], p['col']) for p in pane_keys}
        for panel in panels:
            if not eligible(panel):
                continue
            slot = pane_of.get(panel['id'])
            if slot and (slot['row'], slot['col']) in key_set:
                group_of[panel['id']] = group_idx
    return group_of


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
    link_groups = data.get('linkGroups')
    style = data.get('style') or {}
    layout = data.get('layout') or {}

    if not panels:
        return jsonify({'error': 'no panels to export'}), 400

    rows, columns, pane_of = _resolve_panes(panels, layout)
    group_of = _resolve_link_groups(panels, pane_of, link_groups)

    # Only a non-spatial panel contests the "bottom of column" slot that
    # grants the shared 'time [s]' label -- a spatial panel plots
    # position, not time, and already always gets its own label below, so
    # one sitting at the bottom of a column must not steal that slot away
    # from the time panels above it and leave them all with no label.
    max_row_by_col = {}
    for panel in panels:
        if panel.get('kind') == 'spatial':
            continue
        slot = pane_of[panel['id']]
        bottom = slot['row'] + slot['rowSpan'] - 1
        for c in range(slot['col'], slot['col'] + slot['colSpan']):
            if c not in max_row_by_col or bottom > max_row_by_col[c]:
                max_row_by_col[c] = bottom

    width_px, height_px = layout.get('width'), layout.get('height')
    figsize = (
        width_px / 100 if width_px else max(6, 4.5 * columns),
        height_px / 100 if height_px else max(2.6, 2.6 * rows),
    )

    # rc_context scopes the font override to this figure, rather than
    # mutating matplotlib's global rcParams for every concurrent request.
    font_name = _matplotlib_font(style.get('fontFamily'))
    with plt.rc_context({'font.family': font_name} if font_name else {}):
        fig = plt.figure(figsize=figsize)
        # GridSpec natively supports a subplot spanning multiple cells via
        # slicing -- unlike plt.subplots' uniform (rows, columns) array, so
        # a merged pane just slices a bigger block instead of needing any
        # special-casing here.
        gs = GridSpec(rows, columns, figure=fig)
        first_ax_by_group = {}

        for panel in panels:
            slot = pane_of[panel['id']]
            group = group_of.get(panel['id'])
            ax = fig.add_subplot(
                gs[slot['row']:slot['row'] + slot['rowSpan'], slot['col']:slot['col'] + slot['colSpan']],
                sharex=first_ax_by_group.get(group) if group is not None else None,
            )
            if group is not None and group not in first_ax_by_group:
                first_ax_by_group[group] = ax
            is_bottom = (slot['row'] + slot['rowSpan'] - 1) == max_row_by_col.get(slot['col'])
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
            ax.tick_params(labelsize=style.get('tickFontSize') or 7)
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

            # An explicit label wins regardless of position; otherwise only
            # the bottom-of-column axes gets 'time [s]'.
            if pstyle.get('xlabel'):
                set_xlabel(pstyle['xlabel'], fontsize=style.get('labelFontSize') or 8)
            elif is_bottom:
                set_xlabel('time [s]', fontsize=style.get('labelFontSize') or 8)
            if pstyle.get('ylabel'):
                set_ylabel(pstyle['ylabel'], fontsize=style.get('labelFontSize') or 9)

        if style.get('title'):
            fig.suptitle(style['title'], fontsize=(style.get('labelFontSize') or 9) + 2)
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
