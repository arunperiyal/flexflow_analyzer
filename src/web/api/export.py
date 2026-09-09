"""/api/export — the plot workspace rendered via matplotlib, as PNG (a
chosen dpi, default 300) or PDF (vector; dpi is moot).

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
from matplotlib import font_manager
from matplotlib.ticker import MultipleLocator
from flask import Blueprint, current_app, jsonify, request, send_file

from ..services import registry
from ..services.columns import column_map as build_column_map
from ..services.fft import compute_fft
from ..services.loader import loader
from ..services.spatial import STATS, nearest_time_index, window_mask

bp = Blueprint('export', __name__, url_prefix='/api/export')

# Plotly's line.dash / marker.symbol names, mapped to matplotlib's own
# (unmapped values are left as matplotlib defaults: solid line, no marker).
_LINESTYLES = {'dash': '--', 'dot': ':', 'dashdot': '-.'}
_MARKERS = {'circle': 'o', 'square': 's', 'diamond': 'D', 'cross': '+', 'x': 'x', 'triangle-up': '^'}

# The Style sidebar's font choices (styles.js's FONTS) are named for their
# Windows/macOS originals, which usually aren't installed on a Linux export
# host -- lowercased request name -> a metric-compatible (or close) open
# substitute that IS commonly installed there (checked against the actual
# font list before use, in _matplotlib_font, rather than assumed present).
_FONT_SUBSTITUTES = {
    'times new roman': 'Liberation Serif',
    'arial': 'Liberation Sans',
    'helvetica': 'Nimbus Sans',
    'courier new': 'Liberation Mono',
}


def _matplotlib_font(css_family):
    """A CSS font-family stack (e.g. the style sidebar's '"Times New
    Roman", Times, serif') -> a font name matplotlib can actually render,
    or None to leave its default (DejaVu Sans) alone.

    matplotlib's fontfinder does not error on a missing family -- it just
    silently substitutes DejaVu Sans and prints a warning to stderr
    (invisible from here, since this runs server-side), which is what made
    'Times New Roman' quietly render as a plain sans font with no visible
    error. So the requested name is checked against matplotlib's own
    installed-font list first; if it's missing, a known open substitute is
    tried; and only then does this fall back to the CSS stack's own
    generic keyword (serif/sans-serif/monospace, always its last entry),
    which matplotlib always understands, rather than handing it a specific
    name it's just going to drop silently.
    """
    if not css_family:
        return None
    tokens = [t.strip().strip('"').strip("'") for t in css_family.split(',')]
    tokens = [t for t in tokens if t]
    if not tokens:
        return None

    installed = {f.name for f in font_manager.fontManager.ttflist}
    requested = tokens[0]
    if requested in installed:
        return requested

    substitute = _FONT_SUBSTITUTES.get(requested.lower())
    if substitute and substitute in installed:
        return substitute

    generic = tokens[-1].lower()
    if generic in ('serif', 'sans-serif', 'monospace', 'cursive', 'fantasy'):
        return generic

    return requested   # nothing matched -- matplotlib's own fallback/warning takes it from here


def _pane_rect(panel, layout):
    """A panel's own pane (x, y, w, h -- inches, from Layout -> Panes), or
    the canvas-filling default when it hasn't been placed yet. Python
    mirror of plot.js's PlotArea.paneRect."""
    p = panel.get('pane')
    if isinstance(p, dict) and all(isinstance(p.get(k), (int, float)) for k in ('x', 'y', 'w', 'h')):
        return p
    return {'x': 0, 'y': 0, 'w': layout.get('width') or 6.5, 'h': layout.get('height') or 4.5}


# The same 96 px/in plot.js's SCREEN_DPI renders the browser's on-screen
# figure at -- converts the style's px margins to inches on that same
# scale, so a given margin setting insets the same PHYSICAL amount here as
# it visually does there.
_SCREEN_DPI = 96


def _content_area_in(width_in, height_in, style):
    """The canvas inset by the global margins (inches) -- the same region
    Plotly's own layout.margin carves the plot area out of in the browser.
    A pane's x/y/w/h is expressed in inches of the FULL canvas (see
    paneDomain in plot.js), but Plotly then places that fraction inside
    its margin-inset plot area, never against the paper's own edge -- so
    this is applied here too, in _pane_axes_rect below, rather than mapping
    a pane straight onto the full page. Skipping it left a pane pinned to
    the canvas edge (x=0 is a common, deliberate choice) with literally
    zero room for its own tick labels/axis label, silently clipping them
    off the page now that savefig has no bbox_inches='tight' to expand for it."""
    margin_t = (style.get('marginTop') if style.get('marginTop') is not None
                else (44 if style.get('title') else 24)) / _SCREEN_DPI
    margin_r = (style.get('marginRight') if style.get('marginRight') is not None else 20) / _SCREEN_DPI
    margin_b = (style.get('marginBottom') if style.get('marginBottom') is not None else 40) / _SCREEN_DPI
    margin_l = (style.get('marginLeft') if style.get('marginLeft') is not None else 60) / _SCREEN_DPI
    return {
        'x0': margin_l, 'y0': margin_t,
        'w': max(width_in - margin_l - margin_r, 0.01),
        'h': max(height_in - margin_t - margin_b, 0.01),
    }


def _pane_axes_rect(pane, width_in, height_in, content):
    """A pane's inches rect -> a matplotlib add_axes rect (figure-fraction
    [left, bottom, width, height], y counting up from the bottom). The
    pane's own fraction of the full canvas is placed inside `content` (see
    _content_area_in) before converting to a figure-fraction, mirroring
    how Plotly places a `domain` fraction inside its margin-inset plot
    area rather than against the paper edge. Clamped the same way plot.js's
    paneDomain is -- a pane typed past the canvas edge, or with zero/
    negative size, still renders instead of raising."""
    fx0 = pane['x'] / width_in
    fx1 = (pane['x'] + pane['w']) / width_in
    fy_top = pane['y'] / height_in
    fy_bottom = (pane['y'] + pane['h']) / height_in

    left_in = content['x0'] + fx0 * content['w']
    right_in = content['x0'] + fx1 * content['w']
    top_in = content['y0'] + fy_top * content['h']
    bottom_in = content['y0'] + fy_bottom * content['h']

    left = min(max(left_in / width_in, 0), 1)
    right = min(max(right_in / width_in, 0), 1)
    bottom = min(max(1 - bottom_in / height_in, 0), 1)
    top = min(max(1 - top_in / height_in, 0), 1)
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
    # A trace's own width wins; otherwise the Style sidebar's global one;
    # otherwise this renderer's own baseline (1.0 here, matching what the
    # export already looked like before either override existed -- distinct
    # from plot.js's own baseline of 1.4, a pre-existing difference between
    # the two renderers this doesn't try to unify).
    width = trace.get('lineWidth')
    if width is None:
        width = style.get('lineWidth')
    if width is None:
        width = 1.0
    kwargs = {'linewidth': width, 'linestyle': _LINESTYLES.get(trace.get('lineStyle'), '-')}
    marker = trace.get('marker')
    if marker and marker != 'none':
        kwargs['marker'] = _MARKERS.get(marker, 'o')
        kwargs['markersize'] = style.get('markerSize') or 4
        if style.get('markerStep', 0) > 1:
            kwargs['markevery'] = int(style['markerStep'])
    return kwargs


# dpi only affects PNG (a raster format); a PDF's paths and text stay
# vector regardless, so it's not offered for that format at all (see
# Export -> Format in layout.js) -- but a value arriving anyway (e.g. a
# stale/hand-built request) is still clamped rather than trusted outright,
# the same as PNG's, since matplotlib will happily try to rasterize any
# embedded raster content in a PDF at whatever dpi it's given too.
_MIN_DPI = 50
_MAX_DPI = 1200
_MIMETYPES = {'png': 'image/png', 'pdf': 'application/pdf'}


@bp.post('')
def export_plot():
    root = current_app.config['WORKSPACE_ROOT']
    data = request.get_json(silent=True) or {}
    panels = data.get('panels') or []
    style = data.get('style') or {}
    layout = data.get('layout') or {}

    if not panels:
        return jsonify({'error': 'no panels to export'}), 400

    fmt = (data.get('format') or 'png').lower()
    if fmt not in _MIMETYPES:
        return jsonify({'error': f"unsupported format: {fmt!r} (must be png or pdf)"}), 400

    dpi = data.get('dpi')
    try:
        dpi = 300 if dpi is None else int(dpi)
    except (TypeError, ValueError):
        return jsonify({'error': 'dpi must be a number'}), 400
    dpi = max(_MIN_DPI, min(_MAX_DPI, dpi))

    width_in = layout.get('width') or 6.5
    height_in = layout.get('height') or 4.5
    figsize = (width_in, height_in)
    content = _content_area_in(width_in, height_in, style)

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
            ax = fig.add_axes(_pane_axes_rect(pane, width_in, height_in, content))
            pstyle = panel.get('style') or {}

            # Swap X/Y rotates the panel 90 degrees: pstyle's x*/y* fields
            # always describe the same logical quantity (time/position on X,
            # the plotted value on Y) regardless of swap -- swap only
            # decides which physical matplotlib axis (ax.xaxis vs ax.yaxis)
            # each one lands on, mirroring plot.js's logicalX/logicalY split.
            swap = bool(pstyle.get('swapAxes'))
            plotted = 0
            # Lazily created: a panel with no secondary-axis trace never
            # gets a twin axis at all. twiny (not twinx) when swapped -- the
            # secondary axis is always the *value* one, and swap is what
            # decides whether that's matplotlib's y (twinx) or x (twiny).
            ax2 = None

            def _target_ax(trace):
                nonlocal ax2
                if not trace.get('secondaryAxis'):
                    return ax
                if ax2 is None:
                    ax2 = ax.twiny() if swap else ax.twinx()
                return ax2

            if panel.get('kind') == 'spatial':
                traces = panel.get('traces') or []
                ax_label = (traces[0].get('axLabel') if traces else None) or 'position'
                for trace in traces:
                    xs, ys = _spatial_trace_values(root, trace)
                    if xs is None:
                        continue
                    ys = [y * _scale_of(trace) for y in ys]
                    first, second = (ys, xs) if swap else (xs, ys)
                    label = _label_of(trace, _spatial_trace_label(trace))
                    _target_ax(trace).plot(first, second, color=trace.get('color'), label=label,
                                           **_plot_kwargs(trace, style))
                    plotted += 1
                default_xlabel = ax_label
            elif panel.get('kind') == 'fft':
                for trace in panel.get('traces') or []:
                    freqs, amplitude = _fft_trace_values(root, trace)
                    if freqs is None:
                        continue
                    amplitude = amplitude * _scale_of(trace)
                    freqs = freqs * _xscale_of(trace)
                    first, second = (amplitude, freqs) if swap else (freqs, amplitude)
                    label = _label_of(trace, _fft_auto_label(trace))
                    _target_ax(trace).plot(first, second, color=trace.get('color'), label=label,
                                           **_plot_kwargs(trace, style))
                    plotted += 1
                default_xlabel = 'frequency [Hz]'
            else:
                for trace in panel.get('traces') or []:
                    values, times = _trace_values(root, trace)
                    if values is None:
                        continue
                    values = values * _scale_of(trace)
                    first, second = (values, times) if swap else (times, values)
                    # A surface trace's row is always 0 -- "r0" identifies
                    # nothing a reader could use, unlike a nodal trace's row.
                    # Its block name does instead, matching plot.js.
                    auto_label = (f"{trace.get('case')} {trace.get('block')} {trace.get('col')}"
                                 if trace.get('source') == 'oisd'
                                 else f"{trace.get('case')} r{trace.get('row')} {trace.get('col')}")
                    label = _label_of(trace, auto_label)
                    _target_ax(trace).plot(first, second, color=trace.get('color'), label=label,
                                           **_plot_kwargs(trace, style))
                    plotted += 1
                default_xlabel = 'time [s]'

            _style_panel_axes(ax, pstyle, style, swap, plotted, default_xlabel, panel.get('title'),
                              font_name, ax2=ax2)

        if style.get('title'):
            fig.suptitle(style['title'], fontsize=(style.get('labelFontSize') or 9) + 2)
        # No tight_layout()/bbox_inches='tight' -- both would resize or
        # recrop the figure away from the exact (width_in, height_in)
        # canvas the panes were positioned against, which is the whole
        # point of typing an explicit rect per panel in Layout -> Panes.

        buf = io.BytesIO()
        fig.savefig(buf, dpi=dpi, format=fmt)
        plt.close(fig)
        buf.seek(0)

    download_name = f'flexflow_plot.{fmt}'
    return send_file(buf, mimetype=_MIMETYPES[fmt], as_attachment=True, download_name=download_name)


def _trace_values(root, trace):
    """(values, times) for one trace, or (None, None) if it cannot be read.

    `source` ('othd', the default, or 'oisd' for a surface trace) picks which
    files loader reads -- othId and osgId are both plain integers starting at
    0, so a surface trace's `group` must never be read against the othd cache.
    """
    case_dir = registry.case_path(root, trace.get('case') or '')
    if case_dir is None:
        return None, None
    kind = trace.get('source') or 'othd'
    try:
        meta = loader.meta(case_dir, kind=kind)
        group = trace.get('group')
        cmap = build_column_map(meta, group)
        var_name, comp = cmap[trace.get('col')]
        meta, arrays = loader.load(case_dir, [var_name], group=group, kind=kind)
        row = trace.get('row')
        return arrays[var_name][:, row, comp], meta.times
    except (FileNotFoundError, KeyError, IndexError, TypeError):
        return None, None


def _fft_trace_values(root, trace):
    """(frequencies, amplitude) for one trace's spectrum, or (None, None) if
    it cannot be computed -- reuses _trace_values' own (values, times) read,
    then compute_fft's shared transform (services/fft.py, the same one
    /api/cases/<name>/fft calls), so the export and the live view compute
    this exactly the same way. A non-uniform-time-step case is one more
    reason this can't be read, same silent-skip as every other one here --
    the live /fft endpoint is where that surfaces as a visible error."""
    values, times = _trace_values(root, trace)
    if values is None:
        return None, None
    try:
        return compute_fft(times, values)
    except ValueError:
        return None, None


def _fft_auto_label(trace):
    """Matches plot.js's own autoLabel for an FFT trace -- the same base
    name (surface or nodal) with an ' FFT' suffix, so a spectrum can never
    be mistaken for its own signal's time trace in a legend."""
    base = (f"{trace.get('case')} {trace.get('block')} {trace.get('col')}"
           if trace.get('source') == 'oisd'
           else f"{trace.get('case')} r{trace.get('row')} {trace.get('col')}")
    return f"{base} FFT"


def _spatial_trace_values(root, trace):
    """(xs, ys) for one spatial trace, or (None, None) if it cannot be
    read. xs is the picker's own x, already carried on trace['points']
    (the same one /api/cases/<case>/spatial's caller supplies from the
    browser's own projection -- nothing to recompute here). ys is one
    value per point's row, computed the same way that endpoint does
    (services.spatial): either a single-time snapshot or a stat reduced
    over a time window."""
    case_dir = registry.case_path(root, trace.get('case') or '')
    points = trace.get('points') or []
    if case_dir is None or not points:
        return None, None
    try:
        meta = loader.meta(case_dir)
        group = trace.get('group')
        cmap = build_column_map(meta, group)
        var_name, comp = cmap[trace.get('col')]
        meta, arrays = loader.load(case_dir, [var_name], group=group)
        arr = arrays[var_name]
        rows = [p['row'] for p in points]
        xs = [p['x'] for p in points]
        if trace.get('mode') == 'snapshot':
            t_idx = nearest_time_index(meta.times, trace.get('time'))
            ys = [float(arr[t_idx, row, comp]) for row in rows]
        else:
            mask = window_mask(meta.times, trace.get('t1'), trace.get('t2'))
            stat_fn = STATS[trace.get('stat')]
            ys = [stat_fn(arr[mask, row, comp]) for row in rows]
        return xs, ys
    except (FileNotFoundError, KeyError, IndexError, TypeError, ValueError):
        return None, None


def _spatial_trace_label(trace):
    """Legend text for one spatial trace -- matches plot.js's spatialTraceName."""
    what = f"@t={trace.get('time')}" if trace.get('mode') == 'snapshot' else trace.get('stat')
    return f"{trace.get('case')} {trace.get('col')} {what}"


def _scale_of(trace):
    """A real unit transform (e.g. a force trace turned into a lift
    coefficient) applied to the plotted values, matching plot.js's scaleOf.
    Unset means 1, not 0 -- `trace.get('scale') or 1` would silently turn a
    genuine (if unusual) scale of 0 back into 1."""
    scale = trace.get('scale')
    return 1 if scale is None else scale


def _xscale_of(trace):
    """The same idea as _scale_of, but for an FFT trace's frequency axis --
    matching plot.js's xscaleOf. Only ever read for a kind:'fft' trace."""
    xscale = trace.get('xscale')
    return 1 if xscale is None else xscale


def _label_of(trace, auto_label):
    """The trace's own label override, matching plot.js's labelOf -- an
    empty override falls back to `auto_label` rather than showing nothing."""
    return trace.get('label') or auto_label


def _style_panel_axes(ax, pstyle, style, swap, plotted, default_xlabel, panel_title, font_name, ax2=None):
    """Grid/legend/limits/ticks/labels shared by every panel kind -- mirrors
    plot.js's applyAxisStyle plus the tick/label config render() builds
    around it, including its Y-label fallback to the panel's own title:
    Plotly never draws that title as a heading above the panel (there is
    no "above the panel" in the browser view at all), only ever as the
    Y-axis label's own default when the panel has no explicit ylabel -- so
    neither does this, now that it matches the plot area exactly.

    ax2, when a trace's Axis-tab toggle put it there: the twin axis
    (ax.twinx(), or ax.twiny() if swap -- always whichever one is the
    *value* axis, matching plot.js's secondaryAxis/secondaryKey), styled
    from pstyle's own y2* fields and folded into ax's own legend rather
    than drawing a second one."""
    ax.tick_params(labelsize=style.get('tickFontSize') or 7,
                   direction='in' if style.get('ticksInside') else 'out')
    ax.grid(style.get('showGrid', True))
    # A static PNG has no colored panel-tree to cross-reference trace
    # colors against (unlike the browser view), so unlike there, a legend
    # is shown by default here.
    handles, labels = ax.get_legend_handles_labels()
    if ax2 is not None:
        h2, l2 = ax2.get_legend_handles_labels()
        handles, labels = handles + h2, labels + l2
    if plotted and style.get('showLegend', True):
        ax.legend(handles, labels, fontsize=style.get('legendFontSize') or 6, loc='upper right')

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

    # rc_context's font.family (set once, figure-wide, in export_plot)
    # reaches axis labels, titles and the legend, but NOT tick label Text
    # objects -- a matplotlib quirk already found and worked around the
    # same way in the CLI plot command (apply_plot_properties in
    # src/commands/visualization/plot_impl/command.py: "Set font for tick
    # labels if fontname specified"). Done last, after every call above
    # that can (re)create tick label Text objects -- a custom locator or
    # rotation -- so nothing set here gets regenerated back to the default
    # afterward.
    if font_name:
        for label in x_axis.get_ticklabels() + y_axis.get_ticklabels():
            label.set_fontfamily(font_name)

    # Each panel's tick marks/numbers and axis label are shown or hidden
    # per-panel (Style sidebar's Panel section), not inferred from position.
    if pstyle.get('showXTicks') is False:
        _hide_ticks(ax, x_tick_axis)
    if pstyle.get('showYTicks') is False:
        _hide_ticks(ax, y_tick_axis)

    if pstyle.get('showXLabel') is not False:
        set_xlabel(pstyle.get('xlabel') or default_xlabel, fontsize=style.get('labelFontSize') or 8)
    if pstyle.get('showYLabel') is not False:
        set_ylabel(pstyle.get('ylabel') or panel_title or '', fontsize=style.get('labelFontSize') or 9)

    # The primary axis's own color -- offered once a secondary axis exists
    # (Style sidebar), since only then is there another axis to tell it
    # apart from. Only its own spine ('left', or 'bottom' if swap moved the
    # value role onto the physical x-axis) -- the time/position axis and its
    # spine are untouched, matching plot.js's own ycolor -> logicalYConfig.
    if pstyle.get('ycolor'):
        color = pstyle['ycolor']
        ax.spines['bottom' if swap else 'left'].set_color(color)
        ax.tick_params(axis=y_tick_axis, colors=color)
        y_axis.label.set_color(color)

    if ax2 is not None:
        # No grid of its own -- ax's is enough, and a second set of
        # gridlines on a different scale reads as noise, not information.
        ax2.grid(False)
        ax2.tick_params(labelsize=style.get('tickFontSize') or 7,
                        direction='in' if style.get('ticksInside') else 'out')
        v2_axis = ax2.xaxis if swap else ax2.yaxis
        set_v2_lim = ax2.set_xlim if swap else ax2.set_ylim
        set_v2_label = ax2.set_xlabel if swap else ax2.set_ylabel
        v2_tick_axis = 'x' if swap else 'y'

        if pstyle.get('y2lim'):
            set_v2_lim(pstyle['y2lim'])
        if pstyle.get('y2tick', 0) > 0:
            v2_axis.set_major_locator(MultipleLocator(pstyle['y2tick']))
        if pstyle.get('y2tickangle') is not None:
            ax2.tick_params(axis=v2_tick_axis, labelrotation=pstyle['y2tickangle'])
        if font_name:
            for label in v2_axis.get_ticklabels():
                label.set_fontfamily(font_name)
        if pstyle.get('showY2Ticks') is False:
            _hide_ticks(ax2, v2_tick_axis)
        if pstyle.get('showY2Label') is not False:
            set_v2_label(pstyle.get('y2label') or '', fontsize=style.get('labelFontSize') or 9)

        # Which line belongs to which axis is otherwise only in the legend --
        # tinting the axis spine/ticks/label to match makes that visible
        # right on the figure, mirroring plot.js's own secondaryConfig.color.
        if pstyle.get('y2color'):
            color = pstyle['y2color']
            ax2.spines['top' if swap else 'right'].set_color(color)
            ax2.tick_params(axis=v2_tick_axis, colors=color)
            v2_axis.label.set_color(color)
