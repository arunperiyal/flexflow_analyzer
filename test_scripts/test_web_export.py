"""Tests for POST /api/export -- the workspace rendered via matplotlib at 300 dpi.

Reuses the same trimmed BR0SG0U1P0 fixture as test_web_api.py (no riser.crd,
no binary/ -- this only reads othd_files/ through the loader).
"""

import json
import shutil
from pathlib import Path

import pytest

from src.web.server import create_app

EXAMPLE = Path(__file__).resolve().parent.parent / 'examples' / 'BR0SG0U1P0'
_NEEDED_FILES = ('simflow.config', 'riser.def', 'riser.cyl_nodes.nbc', 'probe_dat.txt',
                 'othd.riser_probe.map', 'othd.riser_probe1_field.map',
                 'riser.cyl.srf', 'riser.cyl.nbc', 'oisd.cylinder_body.map')


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    root = tmp_path_factory.mktemp('web_export_workspace')
    case_dir = root / 'BR0SG0U1P0'
    case_dir.mkdir()
    for name in _NEEDED_FILES:
        shutil.copy(EXAMPLE / name, case_dir / name)
    shutil.copytree(EXAMPLE / 'othd_files', case_dir / 'othd_files')
    shutil.copytree(EXAMPLE / 'oisd_files', case_dir / 'oisd_files')
    (root / '.cases').write_text(json.dumps([{'name': 'BR0SG0U1P0', 'path': str(case_dir)}]))
    return create_app(root).test_client()


def _surface_panels():
    return [{
        'id': 'p1', 'title': 'BR0SG0U1P0 (surface)', 'kind': 'surface',
        'traces': [
            {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'block': 'cylinder_body',
             'col': 'totTrac_x', 'source': 'oisd', 'color': '#dc2626'},
        ],
    }]


def _panels():
    return [{
        'id': 'p1', 'title': 'BR0SG0U1P0',
        'traces': [
            {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'color': '#dc2626'},
            {'case': 'BR0SG0U1P0', 'group': 0, 'row': 12, 'col': 'aleDisp_y', 'color': '#f59e0b'},
        ],
    }]


def test_export_returns_a_png(client):
    res = client.post('/api/export', json={'panels': _panels(), 'linkGroups': None})
    assert res.status_code == 200
    assert res.mimetype == 'image/png'
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'
    assert 'flexflow_plot.png' in res.headers.get('Content-Disposition', '')


def test_trace_values_reads_an_oisd_trace(client):
    from src.web.api.export import _trace_values
    root = client.application.config['WORKSPACE_ROOT']
    trace = {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'totTrac_x', 'source': 'oisd'}
    values, times = _trace_values(root, trace)
    assert values is not None
    assert len(values) == len(times) > 0


def test_trace_values_does_not_read_othd_columns_with_oisd_source(client):
    """group 0 exists in both kinds -- 'source' must be what picks the file
    set, not the group number alone."""
    from src.web.api.export import _trace_values
    root = client.application.config['WORKSPACE_ROOT']
    trace = {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'source': 'oisd'}
    values, times = _trace_values(root, trace)
    assert values is None and times is None


def test_export_renders_a_surface_trace_panel(client):
    res = client.post('/api/export', json={'panels': _surface_panels()})
    assert res.status_code == 200
    assert res.mimetype == 'image/png'
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_with_no_panels_is_a_400(client):
    res = client.post('/api/export', json={'panels': []})
    assert res.status_code == 400


# -- Format (PNG/PDF) and DPI -------------------------------------------

def test_export_defaults_to_png_at_300_dpi_with_no_format_or_dpi_given(client):
    res = client.post('/api/export', json={'panels': _panels()})
    assert res.status_code == 200
    assert res.mimetype == 'image/png'
    assert 'flexflow_plot.png' in res.headers.get('Content-Disposition', '')


def test_export_honors_format_pdf(client):
    res = client.post('/api/export', json={'panels': _panels(), 'format': 'pdf'})
    assert res.status_code == 200
    assert res.mimetype == 'application/pdf'
    assert res.data[:5] == b'%PDF-'
    assert 'flexflow_plot.pdf' in res.headers.get('Content-Disposition', '')


def test_export_rejects_an_unsupported_format(client):
    res = client.post('/api/export', json={'panels': _panels(), 'format': 'svg'})
    assert res.status_code == 400
    assert 'error' in res.get_json()


def test_export_format_is_case_insensitive(client):
    res = client.post('/api/export', json={'panels': _panels(), 'format': 'PDF'})
    assert res.status_code == 200
    assert res.mimetype == 'application/pdf'


def test_export_honors_a_custom_png_dpi(client):
    low = client.post('/api/export', json={'panels': _panels(), 'format': 'png', 'dpi': 72})
    high = client.post('/api/export', json={'panels': _panels(), 'format': 'png', 'dpi': 600})
    assert low.status_code == 200 and high.status_code == 200
    # Not a pixel-exact assertion (compression makes that fragile) -- a
    # rendered PNG at 600 dpi is unambiguously bigger than the same
    # figure at 72 dpi, so this at least proves dpi is actually reaching
    # savefig() and not being silently ignored.
    assert len(high.data) > len(low.data)


def test_export_clamps_a_dpi_outside_the_sane_range(client):
    # An unreasonably high dpi on a several-inch canvas would otherwise
    # try to allocate a huge raster buffer -- clamped rather than trusted,
    # same as a pane rect running off the canvas edge already is.
    from src.web.api.export import _MAX_DPI, _MIN_DPI
    too_high = client.post('/api/export', json={'panels': _panels(), 'format': 'png', 'dpi': 999999})
    too_low = client.post('/api/export', json={'panels': _panels(), 'format': 'png', 'dpi': -5})
    assert too_high.status_code == 200
    assert too_low.status_code == 200
    at_max = client.post('/api/export', json={'panels': _panels(), 'format': 'png', 'dpi': _MAX_DPI})
    at_min = client.post('/api/export', json={'panels': _panels(), 'format': 'png', 'dpi': _MIN_DPI})
    assert too_high.data == at_max.data
    assert too_low.data == at_min.data


def test_export_rejects_a_non_numeric_dpi(client):
    res = client.post('/api/export', json={'panels': _panels(), 'dpi': 'lots'})
    assert res.status_code == 400
    assert 'error' in res.get_json()


def test_export_ignores_dpi_for_pdf_rather_than_erroring(client):
    # dpi is meaningless for a vector format -- accepted and ignored,
    # not rejected, since the dialog only shows the field for PNG and a
    # stray value here shouldn't block an otherwise-valid PDF export.
    res = client.post('/api/export', json={'panels': _panels(), 'format': 'pdf', 'dpi': 999999})
    assert res.status_code == 200
    assert res.mimetype == 'application/pdf'


def test_export_skips_a_trace_from_an_unregistered_case(client):
    panels = [{
        'id': 'p1', 'title': 'ghost',
        'traces': [{'case': 'no-such-case', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'color': '#000'}],
    }]
    res = client.post('/api/export', json={'panels': panels})
    # Renders an (empty) panel rather than erroring the whole export.
    assert res.status_code == 200
    assert res.mimetype == 'image/png'


def test_export_renders_multiple_panels(client):
    panels = _panels() + [{'id': 'p2', 'title': 'second', 'traces': _panels()[0]['traces']}]
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_does_not_crash_on_a_spatial_panel(client):
    # A spatial trace has no `row` (it carries `points` instead) -- naively
    # reusing the time-domain _trace_values() path on it used to misindex
    # the array (row=None shifted `comp` onto the node axis) and raise
    # inside matplotlib's plot(). Now it's routed through
    # _spatial_trace_values() instead (see the correctness tests below).
    panels = [{
        'id': 'p1', 'title': 'spatial rms', 'kind': 'spatial',
        'traces': [{
            'case': 'BR0SG0U1P0', 'group': 0, 'col': 'aleDisp_y', 'mode': 'stat', 'stat': 'rms',
            'points': [{'row': 0, 'x': 0.0}, {'row': 12, 'x': 1.0}], 'color': '#000',
        }],
    }]
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.mimetype == 'image/png'


# -- Spatial panel export -----------------------------------------------

def test_spatial_trace_values_reads_a_snapshot_matching_the_spatial_endpoint(client):
    from src.web.api.export import _spatial_trace_values
    from src.web.services import registry
    from src.web.services.columns import column_map as build_column_map
    from src.web.services.loader import loader
    from src.web.services.spatial import nearest_time_index

    root = client.application.config['WORKSPACE_ROOT']
    trace = {
        'case': 'BR0SG0U1P0', 'group': 0, 'col': 'aleDisp_y', 'mode': 'snapshot', 'time': 1.0,
        'points': [{'row': 0, 'x': 0.0}, {'row': 12, 'x': 1.0}],
    }
    xs, ys = _spatial_trace_values(root, trace)
    assert xs == [0.0, 1.0]

    # Cross-checked against the same read /api/cases/<case>/spatial itself does.
    case_dir = registry.case_path(root, 'BR0SG0U1P0')
    meta = loader.meta(case_dir)
    cmap = build_column_map(meta, 0)
    var_name, comp = cmap['aleDisp_y']
    _, arrays = loader.load(case_dir, [var_name], group=0)
    t_idx = nearest_time_index(meta.times, 1.0)
    expected = [float(arrays[var_name][t_idx, 0, comp]), float(arrays[var_name][t_idx, 12, comp])]
    assert ys == pytest.approx(expected)


def test_spatial_trace_values_reads_a_stat_reduction(client):
    from src.web.api.export import _spatial_trace_values

    root = client.application.config['WORKSPACE_ROOT']
    trace = {
        'case': 'BR0SG0U1P0', 'group': 0, 'col': 'aleDisp_y', 'mode': 'stat', 'stat': 'rms',
        'points': [{'row': 0, 'x': 0.0}, {'row': 12, 'x': 1.0}],
    }
    xs, ys = _spatial_trace_values(root, trace)
    assert xs == [0.0, 1.0]
    assert all(v >= 0 for v in ys)   # rms is non-negative
    assert ys[0] != ys[1]            # two different nodes, not accidentally reading the same row


def test_spatial_trace_values_returns_none_for_an_unregistered_case(client):
    from src.web.api.export import _spatial_trace_values

    root = client.application.config['WORKSPACE_ROOT']
    trace = {'case': 'no-such-case', 'group': 0, 'col': 'aleDisp_y', 'mode': 'snapshot', 'time': 1.0,
              'points': [{'row': 0, 'x': 0.0}]}
    xs, ys = _spatial_trace_values(root, trace)
    assert xs is None and ys is None


def test_spatial_trace_values_returns_none_for_no_points(client):
    from src.web.api.export import _spatial_trace_values
    root = client.application.config['WORKSPACE_ROOT']
    xs, ys = _spatial_trace_values(root, {'case': 'BR0SG0U1P0', 'points': []})
    assert xs is None and ys is None


def test_spatial_trace_label_matches_plot_js_spatial_trace_name():
    from src.web.api.export import _spatial_trace_label
    assert _spatial_trace_label({'case': 'c1', 'col': 'aleDisp_y', 'mode': 'snapshot', 'time': 1.0}) \
        == 'c1 aleDisp_y @t=1.0'
    assert _spatial_trace_label({'case': 'c1', 'col': 'aleDisp_y', 'mode': 'stat', 'stat': 'rms'}) \
        == 'c1 aleDisp_y rms'


# -- Trace scale & label (a real unit transform, not a visual trick) ----

def test_scale_of_defaults_to_1_when_unset():
    from src.web.api.export import _scale_of
    assert _scale_of({}) == 1


def test_scale_of_treats_an_explicit_zero_as_real_not_unset():
    """`trace.get('scale') or 1` would silently turn a genuine 0 back into 1."""
    from src.web.api.export import _scale_of
    assert _scale_of({'scale': 0}) == 0


def test_scale_of_returns_the_explicit_value():
    from src.web.api.export import _scale_of
    assert _scale_of({'scale': 0.25}) == 0.25


def test_label_of_falls_back_to_the_auto_label_when_unset():
    from src.web.api.export import _label_of
    assert _label_of({}, 'auto') == 'auto'


def test_label_of_falls_back_to_the_auto_label_when_empty():
    from src.web.api.export import _label_of
    assert _label_of({'label': ''}, 'auto') == 'auto'


def test_label_of_returns_the_explicit_label():
    from src.web.api.export import _label_of
    assert _label_of({'label': 'Cl'}, 'auto') == 'Cl'


def test_export_scales_a_trace_and_uses_its_custom_label(client, monkeypatch):
    """End-to-end: the values matplotlib actually draws are scaled, and the
    legend uses the override -- not just that the request doesn't crash."""
    import numpy as np
    from matplotlib.axes import Axes
    from src.web.api import export as export_mod

    root = client.application.config['WORKSPACE_ROOT']
    raw_values, _ = export_mod._trace_values(
        root, {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'totTrac_x', 'source': 'oisd'})

    captured = {}
    real_plot = Axes.plot

    def spy_plot(self, *args, **kwargs):
        captured['y'] = args[1]
        captured['label'] = kwargs.get('label')
        return real_plot(self, *args, **kwargs)
    monkeypatch.setattr(Axes, 'plot', spy_plot)

    panels = _surface_panels()
    panels[0]['traces'][0]['scale'] = 2.0
    panels[0]['traces'][0]['label'] = 'Cl'
    res = client.post('/api/export', json={'panels': panels})

    assert res.status_code == 200
    assert captured['label'] == 'Cl'
    np.testing.assert_allclose(captured['y'], np.asarray(raw_values) * 2.0)


def test_export_spatial_trace_scale_and_label(client, monkeypatch):
    from matplotlib.axes import Axes
    from src.web.api import export as export_mod

    root = client.application.config['WORKSPACE_ROOT']
    raw_xs, raw_ys = export_mod._spatial_trace_values(
        root, {'case': 'BR0SG0U1P0', 'group': 0, 'col': 'aleDisp_y', 'mode': 'snapshot', 'time': 0.05,
               'points': [{'row': 0, 'x': 0.0}]})

    captured = {}
    real_plot = Axes.plot

    def spy_plot(self, *args, **kwargs):
        captured['y'] = args[1]
        captured['label'] = kwargs.get('label')
        return real_plot(self, *args, **kwargs)
    monkeypatch.setattr(Axes, 'plot', spy_plot)

    panels = [{
        'id': 'p1', 'title': 'spatial', 'kind': 'spatial',
        'traces': [{
            'case': 'BR0SG0U1P0', 'group': 0, 'col': 'aleDisp_y', 'mode': 'snapshot', 'time': 0.05,
            'points': [{'row': 0, 'x': 0.0}], 'axLabel': 'position', 'color': '#dc2626',
            'scale': 3.0, 'label': 'Cd',
        }],
    }]
    res = client.post('/api/export', json={'panels': panels})

    assert res.status_code == 200
    assert captured['label'] == 'Cd'
    assert captured['y'] == [y * 3.0 for y in raw_ys]


def test_export_renders_actual_spatial_data_not_a_placeholder(client):
    panels = [{
        'id': 'p1', 'title': 'spatial rms', 'kind': 'spatial',
        'traces': [{
            'case': 'BR0SG0U1P0', 'group': 0, 'col': 'aleDisp_y', 'mode': 'stat', 'stat': 'rms',
            'points': [{'row': 0, 'x': 0.0}, {'row': 12, 'x': 1.0}], 'color': '#dc2626',
        }],
    }]
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'
    # Bigger than a near-empty placeholder axes -- a real plotted line plus
    # axis chrome renders meaningfully more PNG data than blank white space.
    assert len(res.data) > 5000


def test_export_honors_swap_axes_on_a_spatial_panel(client):
    panels = [{
        'id': 'p1', 'title': 'swapped', 'kind': 'spatial', 'style': {'swapAxes': True},
        'traces': [{
            'case': 'BR0SG0U1P0', 'group': 0, 'col': 'aleDisp_y', 'mode': 'snapshot', 'time': 1.0,
            'points': [{'row': 0, 'x': 0.0}, {'row': 12, 'x': 1.0}], 'color': '#000',
        }],
    }]
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_mixed_time_and_spatial_panels(client):
    panels = _panels() + [{
        'id': 'p2', 'title': 'spatial', 'kind': 'spatial',
        'traces': [{'case': 'BR0SG0U1P0', 'group': 0, 'col': 'aleDisp_y', 'mode': 'snapshot',
                    'time': 1.0, 'points': [{'row': 0, 'x': 0.0}], 'color': '#000'}],
    }]
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


# -- Secondary (Y2) axis --------------------------------------------------

def test_export_no_twin_axis_when_no_trace_is_secondary(client, monkeypatch):
    from matplotlib.axes import Axes
    calls = []
    real_twinx = Axes.twinx

    def spy_twinx(self):
        calls.append(True)
        return real_twinx(self)
    monkeypatch.setattr(Axes, 'twinx', spy_twinx)

    res = client.post('/api/export', json={'panels': _panels()})
    assert res.status_code == 200
    assert calls == []


def test_export_secondary_trace_lands_on_a_twin_axis_with_its_own_values(client, monkeypatch):
    import numpy as np
    from matplotlib.axes import Axes
    from src.web.api import export as export_mod

    root = client.application.config['WORKSPACE_ROOT']
    raw_values, _ = export_mod._trace_values(
        root, {'case': 'BR0SG0U1P0', 'group': 0, 'row': 12, 'col': 'aleDisp_y'})

    twin_axes = []
    real_twinx = Axes.twinx
    real_plot = Axes.plot
    captured = {'primary': [], 'secondary': []}

    def spy_twinx(self):
        ax2 = real_twinx(self)
        twin_axes.append(ax2)
        return ax2

    def spy_plot(self, *args, **kwargs):
        bucket = 'secondary' if self in twin_axes else 'primary'
        captured[bucket].append(args[1])
        return real_plot(self, *args, **kwargs)

    monkeypatch.setattr(Axes, 'twinx', spy_twinx)
    monkeypatch.setattr(Axes, 'plot', spy_plot)

    panels = _panels()
    panels[0]['traces'][1]['secondaryAxis'] = True
    res = client.post('/api/export', json={'panels': panels})

    assert res.status_code == 200
    assert len(captured['primary']) == 1
    assert len(captured['secondary']) == 1
    np.testing.assert_allclose(captured['secondary'][0], raw_values)


def test_export_swapped_panel_uses_twiny_for_a_secondary_trace(client, monkeypatch):
    from matplotlib.axes import Axes
    calls = {'twinx': 0, 'twiny': 0}
    real_twiny = Axes.twiny

    def spy_twinx(self):
        calls['twinx'] += 1
        raise AssertionError('twinx should not be called for a swapped panel')

    def spy_twiny(self):
        calls['twiny'] += 1
        return real_twiny(self)
    monkeypatch.setattr(Axes, 'twinx', spy_twinx)
    monkeypatch.setattr(Axes, 'twiny', spy_twiny)

    panels = _panels()
    panels[0]['style'] = {'swapAxes': True}
    panels[0]['traces'][1]['secondaryAxis'] = True
    res = client.post('/api/export', json={'panels': panels})

    assert res.status_code == 200
    assert calls == {'twinx': 0, 'twiny': 1}


def test_export_legend_combines_primary_and_secondary_traces(client, monkeypatch):
    from matplotlib.axes import Axes
    captured = {}
    real_legend = Axes.legend

    def spy_legend(self, *args, **kwargs):
        captured['labels'] = args[1] if len(args) > 1 else kwargs.get('labels')
        return real_legend(self, *args, **kwargs)
    monkeypatch.setattr(Axes, 'legend', spy_legend)

    panels = _panels()
    panels[0]['traces'][1]['secondaryAxis'] = True
    panels[0]['traces'][1]['label'] = 'Secondary'
    res = client.post('/api/export', json={'panels': panels, 'style': {'showLegend': True}})

    assert res.status_code == 200
    assert 'Secondary' in captured['labels']


def test_style_panel_axes_sets_y2_label_limit_and_ticks_on_the_twin_axis():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from src.web.api.export import _style_panel_axes

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax2 = ax.twinx()
    ax2.plot([0, 1], [100, 200])
    _style_panel_axes(ax, {'y2label': 'Cl', 'y2lim': [0, 300], 'y2tick': 100}, {}, swap=False,
                      plotted=1, default_xlabel='time [s]', panel_title='p', font_name=None, ax2=ax2)
    fig.canvas.draw()

    assert ax2.get_ylabel() == 'Cl'
    assert ax2.get_ylim() == (0, 300)
    assert [t for t in ax2.get_yticks() if 0 <= t <= 300] == [0, 100, 200, 300]
    plt.close(fig)


def test_style_panel_axes_hides_the_twin_axis_ticks_and_label_when_asked():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from src.web.api.export import _style_panel_axes

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax2 = ax.twinx()
    ax2.plot([0, 1], [100, 200])
    _style_panel_axes(ax, {'showY2Ticks': False, 'showY2Label': False}, {}, swap=False, plotted=1,
                      default_xlabel='time [s]', panel_title='p', font_name=None, ax2=ax2)
    fig.canvas.draw()

    assert ax2.get_ylabel() == ''
    assert not any(t.get_visible() for t in ax2.get_yticklabels())
    plt.close(fig)


def test_style_panel_axes_never_shows_a_grid_on_the_twin_axis():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from src.web.api.export import _style_panel_axes

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax2 = ax.twinx()
    ax2.plot([0, 1], [100, 200])
    _style_panel_axes(ax, {}, {'showGrid': True}, swap=False, plotted=1, default_xlabel='time [s]',
                      panel_title='p', font_name=None, ax2=ax2)
    fig.canvas.draw()

    assert not any(line.get_visible() for line in ax2.yaxis.get_gridlines())
    plt.close(fig)


def test_style_panel_axes_colors_the_twin_axis_spine_ticks_and_label():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import to_rgba
    from src.web.api.export import _style_panel_axes

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax2 = ax.twinx()
    ax2.plot([0, 1], [100, 200])
    _style_panel_axes(ax, {'y2color': '#0891b2', 'y2label': 'Cl'}, {}, swap=False, plotted=1,
                      default_xlabel='time [s]', panel_title='p', font_name=None, ax2=ax2)
    fig.canvas.draw()

    expected = to_rgba('#0891b2')
    assert to_rgba(ax2.spines['right'].get_edgecolor()) == expected
    assert to_rgba(ax2.yaxis.label.get_color()) == expected
    assert {to_rgba(t.get_color()) for t in ax2.get_yticklabels()} == {expected}
    # The primary axis is untouched -- only ax2 was told to tint itself.
    assert to_rgba(ax.yaxis.label.get_color()) != expected
    plt.close(fig)


def test_style_panel_axes_colors_the_top_spine_when_swapped():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import to_rgba
    from src.web.api.export import _style_panel_axes

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax2 = ax.twiny()
    ax2.plot([100, 200], [0, 1])
    _style_panel_axes(ax, {'y2color': '#dc2626'}, {}, swap=True, plotted=1,
                      default_xlabel='position', panel_title='p', font_name=None, ax2=ax2)
    fig.canvas.draw()

    assert to_rgba(ax2.spines['top'].get_edgecolor()) == to_rgba('#dc2626')
    plt.close(fig)


def test_style_panel_axes_leaves_the_twin_axis_default_colored_when_unset():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from src.web.api.export import _style_panel_axes

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax2 = ax.twinx()
    ax2.plot([0, 1], [100, 200])
    default_edgecolor = ax2.spines['right'].get_edgecolor()
    _style_panel_axes(ax, {}, {}, swap=False, plotted=1, default_xlabel='time [s]',
                      panel_title='p', font_name=None, ax2=ax2)
    fig.canvas.draw()

    assert ax2.spines['right'].get_edgecolor() == default_edgecolor
    plt.close(fig)


def test_style_panel_axes_colors_the_primary_axis_spine_ticks_and_label():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import to_rgba
    from src.web.api.export import _style_panel_axes

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax2 = ax.twinx()
    ax2.plot([0, 1], [100, 200])
    _style_panel_axes(ax, {'ycolor': '#dc2626', 'ylabel': 'aleDisp_y'}, {}, swap=False, plotted=1,
                      default_xlabel='time [s]', panel_title='p', font_name=None, ax2=ax2)
    fig.canvas.draw()

    expected = to_rgba('#dc2626')
    assert to_rgba(ax.spines['left'].get_edgecolor()) == expected
    assert to_rgba(ax.yaxis.label.get_color()) == expected
    assert {to_rgba(t.get_color()) for t in ax.get_yticklabels()} == {expected}
    # The secondary axis is untouched -- only ax was told to tint itself.
    assert to_rgba(ax2.yaxis.label.get_color()) != expected
    plt.close(fig)


def test_style_panel_axes_colors_the_primary_bottom_spine_when_swapped():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import to_rgba
    from src.web.api.export import _style_panel_axes

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    _style_panel_axes(ax, {'ycolor': '#0891b2'}, {}, swap=True, plotted=1,
                      default_xlabel='position', panel_title='p', font_name=None)
    fig.canvas.draw()

    assert to_rgba(ax.spines['bottom'].get_edgecolor()) == to_rgba('#0891b2')
    plt.close(fig)


def test_style_panel_axes_leaves_the_primary_axis_default_colored_when_unset():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from src.web.api.export import _style_panel_axes

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    default_edgecolor = ax.spines['left'].get_edgecolor()
    _style_panel_axes(ax, {}, {}, swap=False, plotted=1, default_xlabel='time [s]',
                      panel_title='p', font_name=None)
    fig.canvas.draw()

    assert ax.spines['left'].get_edgecolor() == default_edgecolor
    plt.close(fig)


# -- style sidebar settings, carried through to the matplotlib render -------

def test_export_honors_global_style(client):
    style = {
        'fontFamily': 'DejaVu Sans', 'labelFontSize': 14, 'legendFontSize': 8,
        'title': 'Riser response', 'showLegend': True, 'showGrid': False,
    }
    res = client.post('/api/export', json={'panels': _panels(), 'style': style})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_honors_panel_xlim_ylim_and_ticks(client):
    panels = _panels()
    panels[0]['style'] = {'xlim': [0, 50], 'ylim': [-1, 1], 'xtick': 10, 'ytick': 0.5}
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_ignores_a_negative_tick_step_instead_of_crashing(client):
    # MultipleLocator raises ValueError for a non-positive base; a `truthy`
    # check alone lets a negative value through (only 0 is falsy in Python).
    panels = _panels()
    panels[0]['style'] = {'xtick': -5, 'ytick': -1}
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_with_no_style_key_at_all_still_works(client):
    # The pre-style-sidebar request shape -- no `style` field in the body.
    res = client.post('/api/export', json={'panels': _panels()})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_honors_tick_font_size(client):
    res = client.post('/api/export', json={'panels': _panels(), 'style': {'tickFontSize': 12}})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_honors_panel_xlabel_ylabel_and_tick_angle(client):
    panels = _panels()
    panels[0]['style'] = {'xlabel': 'Time [s]', 'ylabel': 'Displacement [m]', 'xtickangle': 45, 'ytickangle': -30}
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_xlabel_on_a_non_last_panel_still_shows(client):
    # The bottom axes gets the default 'time [s]' label; any other panel
    # only gets a label if it explicitly asks for one.
    panels = _panels() + [{'id': 'p2', 'title': 'second', 'traces': _panels()[0]['traces'],
                           'style': {'xlabel': 'Custom x'}}]
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_honors_per_trace_line_style_marker_and_color(client):
    panels = _panels()
    panels[0]['traces'][0]['lineStyle'] = 'dashdot'
    panels[0]['traces'][0]['marker'] = 'triangle-up'
    panels[0]['traces'][0]['color'] = '#123456'
    panels[0]['traces'][1]['lineStyle'] = 'dot'
    panels[0]['traces'][1]['marker'] = 'none'
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_honors_global_marker_size_and_step(client):
    panels = _panels()
    panels[0]['traces'][0]['marker'] = 'circle'
    res = client.post('/api/export', json={
        'panels': panels, 'style': {'markerSize': 10, 'markerStep': 25},
    })
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_plot_kwargs_maps_marker_size_and_step_onto_matplotlib_names():
    from src.web.api.export import _plot_kwargs

    trace = {'marker': 'circle'}
    kwargs = _plot_kwargs(trace, {'markerSize': 10, 'markerStep': 25})
    assert kwargs['markersize'] == 10
    assert kwargs['markevery'] == 25

    # No marker on the trace at all -- size/step are moot, no markevery/markersize leak in.
    kwargs_no_marker = _plot_kwargs({}, {'markerSize': 10, 'markerStep': 25})
    assert 'markevery' not in kwargs_no_marker
    assert 'markersize' not in kwargs_no_marker

    # A marker with no global override falls back to the existing default.
    kwargs_default = _plot_kwargs({'marker': 'circle'}, {})
    assert kwargs_default['markersize'] == 4
    assert 'markevery' not in kwargs_default

    # step of 1 (or unset) means "every point" -- matches Plotly's step<=1 no-op, not markevery=1.
    kwargs_step1 = _plot_kwargs({'marker': 'circle'}, {'markerStep': 1})
    assert 'markevery' not in kwargs_step1


def test_plot_kwargs_line_width_falls_back_trace_then_global_then_default():
    from src.web.api.export import _plot_kwargs

    assert _plot_kwargs({'lineWidth': 3.0}, {'lineWidth': 2.0})['linewidth'] == 3.0
    assert _plot_kwargs({}, {'lineWidth': 2.0})['linewidth'] == 2.0
    assert _plot_kwargs({}, {})['linewidth'] == 1.0
    # A trace explicitly at 0 is a real (if unusual) width, not "unset".
    assert _plot_kwargs({'lineWidth': 0.5}, {'lineWidth': 2.0})['linewidth'] == 0.5


def test_export_honors_per_trace_and_global_line_width(client, monkeypatch):
    from matplotlib.axes import Axes
    captured = []
    real_plot = Axes.plot

    def spy_plot(self, *args, **kwargs):
        captured.append(kwargs.get('linewidth'))
        return real_plot(self, *args, **kwargs)
    monkeypatch.setattr(Axes, 'plot', spy_plot)

    panels = _panels()
    panels[0]['traces'][0]['lineWidth'] = 3.5   # per-trace override wins
    res = client.post('/api/export', json={'panels': panels, 'style': {'lineWidth': 2.0}})

    assert res.status_code == 200
    assert captured == [3.5, 2.0]


def test_matplotlib_font_returns_none_for_no_font_family():
    from src.web.api.export import _matplotlib_font
    assert _matplotlib_font('') is None
    assert _matplotlib_font(None) is None


def test_matplotlib_font_returns_an_already_installed_name_unchanged():
    # No need to substitute or fall back when the exact requested name is
    # right there in matplotlib's own font list.
    from matplotlib import font_manager
    from src.web.api.export import _matplotlib_font
    installed_name = next(iter({f.name for f in font_manager.fontManager.ttflist}))
    assert _matplotlib_font(f'"{installed_name}", serif') == installed_name


def test_matplotlib_font_prefers_an_installed_substitute_over_a_missing_windows_font(monkeypatch):
    # The style sidebar's font dropdown sends CSS font-family syntax (e.g.
    # '"Times New Roman", Times, serif') naming Windows/macOS fonts that
    # are often missing on a Linux export host -- matplotlib silently
    # substitutes DejaVu Sans for any it can't find rather than raising or
    # warning anywhere visible, which is exactly why 'Times New Roman'
    # used to render as a plain sans font with no error. Each of these
    # should resolve to its metric-compatible open substitute instead, when
    # the real font is missing but the substitute is installed.
    #
    # The exact fonts this host has vary (this one now has the real
    # Microsoft core fonts installed -- see Settings -> Clear Cache, added
    # after this app first hit that gap), so the "requested font missing"
    # half of that condition is faked here via a stand-in installed set,
    # rather than relying on it happening to be true of whatever box the
    # suite runs on.
    from types import SimpleNamespace
    from matplotlib import font_manager
    from src.web.api.export import _matplotlib_font, _FONT_SUBSTITUTES

    fake_installed = [SimpleNamespace(name=n) for n in _FONT_SUBSTITUTES.values()]
    monkeypatch.setattr(font_manager.fontManager, 'ttflist', fake_installed)

    for requested, substitute in _FONT_SUBSTITUTES.items():
        css = f'"{requested.title()}", serif'
        assert _matplotlib_font(css) == substitute


def test_matplotlib_font_falls_back_to_the_css_stacks_generic_keyword():
    # A font with neither an install nor a known substitute (made up, so
    # it can never collide with something actually present) falls back to
    # the CSS stack's own trailing generic keyword -- serif/sans-serif/
    # monospace -- which matplotlib always understands, rather than being
    # handed a specific name it will just drop silently.
    from src.web.api.export import _matplotlib_font
    assert _matplotlib_font('"Definitely Not A Real Font XYZ", sans-serif') == 'sans-serif'
    assert _matplotlib_font('"Also Not Real ABC", serif') == 'serif'
    assert _matplotlib_font('"Nor This One", monospace') == 'monospace'


def test_export_honors_every_style_sidebar_font_choice(client):
    # Every font the Style sidebar's dropdown (styles.js's FONTS) can send
    # should resolve to something matplotlib can actually render -- an
    # installed name or a generic family keyword -- not silently collapse
    # to whichever font.family happens to already be the default.
    from matplotlib import font_manager
    from src.web.api.export import _matplotlib_font

    stacks = [
        'Arial, sans-serif',
        'Helvetica, Arial, sans-serif',
        'Georgia, serif',
        '"Times New Roman", Times, serif',
        '"Courier New", Courier, monospace',
        'Verdana, sans-serif',
        '"Trebuchet MS", sans-serif',
        '"Segoe UI", Roboto, sans-serif',
        '"DejaVu Sans Mono", monospace',
    ]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    generic = {'serif', 'sans-serif', 'monospace', 'cursive', 'fantasy'}
    for css in stacks:
        resolved = _matplotlib_font(css)
        assert resolved in installed or resolved in generic, f"{css!r} resolved to unusable {resolved!r}"

    res = client.post('/api/export', json={
        'panels': _panels(), 'style': {'fontFamily': '"Times New Roman", Times, serif'},
    })
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_style_panel_axes_sets_tick_label_font_family_directly():
    # Regression: matplotlib's rc_context({'font.family': ...}) reaches
    # axis labels, titles and the legend, but NOT tick label Text objects
    # -- a quirk already found and worked around the same way in the CLI
    # plot command (apply_plot_properties, src/commands/visualization/
    # plot_impl/command.py: "Set font for tick labels if fontname
    # specified"). Without the same fix here, the axis numbers silently
    # stayed in matplotlib's default font while every other piece of text
    # on the figure switched to the requested one.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from src.web.api.export import _style_panel_axes

    with plt.rc_context({'font.family': 'Liberation Serif'}):
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        _style_panel_axes(ax, {}, {}, swap=False, plotted=0, default_xlabel='time [s]',
                          panel_title='p', font_name='Liberation Serif')
        fig.canvas.draw()
        tick_labels = ax.get_xticklabels() + ax.get_yticklabels()
        assert tick_labels   # the axes actually has ticks to check
        for label in tick_labels:
            assert label.get_fontfamily() == ['Liberation Serif']
        plt.close(fig)


def test_style_panel_axes_leaves_tick_font_alone_when_no_font_requested():
    # font_name is None (the Style sidebar's "Default" option) -- nothing
    # here should force a font choice matplotlib wasn't asked for.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from src.web.api.export import _style_panel_axes

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    default_family = plt.rcParams['font.family']
    _style_panel_axes(ax, {}, {}, swap=False, plotted=0, default_xlabel='time [s]',
                      panel_title='p', font_name=None)
    fig.canvas.draw()
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        assert label.get_fontfamily() == default_family
    plt.close(fig)


# -- swap X/Y ------------------------------------------------------------

def test_export_swap_axes_with_all_style_fields_set(client):
    # xlim/ylim/xtick/ytick/xlabel/ylabel/tickangle all still describe the
    # logical X/Y quantity when swapped -- this exercises every one of
    # them landing on the *other* physical matplotlib axis without raising.
    panels = _panels()
    panels[0]['style'] = {
        'swapAxes': True,
        'xlim': [0, 50], 'ylim': [-1, 1],
        'xtick': 10, 'ytick': 0.5,
        'xtickangle': 45, 'ytickangle': -30,
        'xlabel': 'Time [s]', 'ylabel': 'Displacement [m]',
    }
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_swap_axes_with_no_other_overrides(client):
    panels = _panels()
    panels[0]['style'] = {'swapAxes': True}
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_swap_axes_on_the_last_panel_still_gets_a_default_label(client):
    # The default 'time [s]' label normally lands on the bottom axes' x
    # label; swapped, it should land on that axes' y label instead, not
    # silently disappear.
    panels = _panels()
    panels[0]['style'] = {'swapAxes': True}
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200


# -- LaTeX -----------------------------------------------------------------

def test_export_renders_dollar_wrapped_text_via_matplotlibs_own_mathtext(client):
    # No server-side flag needed for this: matplotlib auto-typesets $...$
    # text with its own mathtext engine regardless of any setting, unlike
    # Plotly which needs MathJax loaded first. This just confirms passing
    # such text through doesn't raise.
    res = client.post('/api/export', json={
        'panels': _panels(), 'style': {'title': r'$\alpha$ vs $\beta$'},
    })
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


# -- Pane position/size (Layout -> Panes) -----------------------------------

def test_pane_rect_uses_explicit_xywh_when_present():
    from src.web.api.export import _pane_rect

    panel = {'id': 'p1', 'pane': {'x': 1, 'y': 0.5, 'w': 2, 'h': 1.5}}
    assert _pane_rect(panel, {'width': 6.5, 'height': 4.5}) == {'x': 1, 'y': 0.5, 'w': 2, 'h': 1.5}


def test_pane_rect_defaults_to_filling_the_canvas_when_unset():
    from src.web.api.export import _pane_rect

    assert _pane_rect({'id': 'p1', 'pane': None}, {'width': 6.5, 'height': 4.5}) == \
        {'x': 0, 'y': 0, 'w': 6.5, 'h': 4.5}
    assert _pane_rect({'id': 'p1'}, {'width': 6.5, 'height': 4.5}) == \
        {'x': 0, 'y': 0, 'w': 6.5, 'h': 4.5}
    # A stale/legacy shape (e.g. the old {row, col}) is not free-form either.
    assert _pane_rect({'id': 'p1', 'pane': {'row': 0, 'col': 1}}, {'width': 6.5, 'height': 4.5}) == \
        {'x': 0, 'y': 0, 'w': 6.5, 'h': 4.5}


_ZERO_MARGIN_CONTENT = {'x0': 0, 'y0': 0, 'w': 6, 'h': 4}   # the full 6x4in canvas, no inset


def test_pane_axes_rect_maps_inches_to_a_figure_fraction_rect():
    from src.web.api.export import _pane_axes_rect

    # Top-left quarter of a 6x4in canvas -> left=0, bottom=0.5 (y counts up
    # from the bottom, inches count down from the top), width=0.5, height=0.5.
    rect = _pane_axes_rect({'x': 0, 'y': 0, 'w': 3, 'h': 2}, width_in=6, height_in=4, content=_ZERO_MARGIN_CONTENT)
    assert rect == [0, 0.5, 0.5, 0.5]


def test_pane_axes_rect_clamps_a_pane_that_runs_past_the_canvas_edge():
    from src.web.api.export import _pane_axes_rect

    # A pane wider than the canvas itself must not hand matplotlib a
    # fraction outside [0, 1] -- clamped rather than raising.
    rect = _pane_axes_rect({'x': 0, 'y': 0, 'w': 20, 'h': 2}, width_in=6, height_in=4, content=_ZERO_MARGIN_CONTENT)
    left, bottom, width, height = rect
    assert 0 <= left <= 1 and 0 <= left + width <= 1


def test_content_area_in_insets_by_the_style_margins_in_inches():
    from src.web.api.export import _content_area_in, _SCREEN_DPI

    # Default margins (no style overrides, no title): t=24px, r=20px, b=40px, l=60px.
    content = _content_area_in(6.5, 4.5, {})
    assert content['x0'] == pytest.approx(60 / _SCREEN_DPI)
    assert content['y0'] == pytest.approx(24 / _SCREEN_DPI)
    assert content['w'] == pytest.approx(6.5 - 60 / _SCREEN_DPI - 20 / _SCREEN_DPI)
    assert content['h'] == pytest.approx(4.5 - 24 / _SCREEN_DPI - 40 / _SCREEN_DPI)


def test_content_area_in_honors_explicit_margin_overrides():
    from src.web.api.export import _content_area_in, _SCREEN_DPI

    content = _content_area_in(6, 4, {'marginTop': 10, 'marginRight': 10, 'marginBottom': 10, 'marginLeft': 96})
    assert content['x0'] == pytest.approx(1.0)   # 96px / 96 px-per-in == 1in
    assert content['y0'] == pytest.approx(10 / _SCREEN_DPI)


def test_pane_at_the_canvas_edge_still_lands_inside_the_margin_not_the_paper_edge():
    # Regression: a pane pinned to x=0 (a common, deliberate choice -- see
    # Layout -> Panes) used to map straight onto the literal PNG paper edge,
    # leaving matplotlib zero room to draw that axes' own y-tick labels/
    # y-axis label, which were then silently clipped off the saved image
    # (no bbox_inches='tight' to expand the page for them anymore).
    from src.web.api.export import _pane_axes_rect, _content_area_in

    width_in, height_in = 6.5, 4.5
    content = _content_area_in(width_in, height_in, {})
    left, bottom, width, height = _pane_axes_rect(
        {'x': 0, 'y': 0, 'w': width_in, 'h': height_in}, width_in, height_in, content)
    assert left > 0   # room reserved to the left for tick labels/axis label
    assert bottom > 0   # ... and below, for the x-axis's own labels


def test_export_honors_explicit_pane_positions(client):
    panels = [
        {'id': 'p1', 'title': 'left', 'traces': _panels()[0]['traces'], 'pane': {'x': 0, 'y': 0, 'w': 3, 'h': 4}},
        {'id': 'p2', 'title': 'right', 'traces': _panels()[0]['traces'], 'pane': {'x': 3, 'y': 0, 'w': 3, 'h': 4}},
    ]
    res = client.post('/api/export', json={'panels': panels, 'layout': {'width': 6, 'height': 4}})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_defaults_a_panel_with_no_pane_to_filling_the_canvas(client):
    res = client.post('/api/export', json={'panels': _panels(), 'layout': {'width': 5, 'height': 3}})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_does_not_crash_on_a_pane_that_overlaps_or_overruns_the_canvas(client):
    # Free-form panes may overlap each other, or a typo/out-of-range value
    # may run one past the canvas edge -- neither should break the export.
    panels = [
        {'id': 'p1', 'title': 'overlap-a', 'traces': _panels()[0]['traces'], 'pane': {'x': 0, 'y': 0, 'w': 5, 'h': 3}},
        {'id': 'p2', 'title': 'overlap-b', 'traces': _panels()[0]['traces'], 'pane': {'x': 1, 'y': 1, 'w': 5, 'h': 3}},
        {'id': 'p3', 'title': 'off-canvas', 'traces': _panels()[0]['traces'], 'pane': {'x': -1, 'y': -1, 'w': 20, 'h': 20}},
    ]
    res = client.post('/api/export', json={'panels': panels, 'layout': {'width': 5, 'height': 3}})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_a_spatial_panel_does_not_crash(client):
    panels = [
        {'id': 'p1', 'title': 'time', 'traces': _panels()[0]['traces'], 'pane': {'x': 0, 'y': 0, 'w': 6, 'h': 2}},
        {'id': 'p2', 'title': 'spatial', 'kind': 'spatial', 'pane': {'x': 0, 'y': 2, 'w': 6, 'h': 2},
         'traces': [{'case': 'BR0SG0U1P0', 'group': 0, 'col': 'aleDisp_y', 'mode': 'snapshot',
                     'time': 1.0, 'points': [{'row': 0, 'x': 0.0}], 'color': '#000'}]},
    ]
    res = client.post('/api/export', json={'panels': panels, 'layout': {'width': 6, 'height': 4}})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


# -- Per-panel tick/label visibility -----------------------------------------

def test_hide_ticks_hides_marks_and_labels_on_the_requested_physical_axis():
    from src.web.api.export import _hide_ticks
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    _hide_ticks(ax, 'x')
    x_params = ax.xaxis.get_tick_params()
    assert x_params['bottom'] is False and x_params['labelbottom'] is False
    # The y axis is untouched by hiding x.
    y_params = ax.yaxis.get_tick_params()
    assert y_params['left'] is not False

    _hide_ticks(ax, 'y')
    y_params = ax.yaxis.get_tick_params()
    assert y_params['left'] is False and y_params['labelleft'] is False
    plt.close(fig)


def test_export_honors_show_x_ticks_false(client):
    panels = _panels()
    panels[0]['style'] = {'showXTicks': False}
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_honors_show_y_ticks_false(client):
    panels = _panels()
    panels[0]['style'] = {'showYTicks': False}
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_honors_show_x_label_false(client):
    panels = _panels()
    panels[0]['style'] = {'showXLabel': False}
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_honors_show_y_label_false(client):
    panels = _panels()
    panels[0]['style'] = {'showYLabel': False, 'ylabel': 'Displacement [m]'}
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_defaults_to_showing_time_label_on_every_panel(client):
    # No more "only the bottom of the column" heuristic -- every time
    # panel defaults to showing 'time [s]' unless its own showXLabel is
    # explicitly turned off.
    panels = [
        {'id': 'p1', 'title': 'first', 'traces': _panels()[0]['traces'], 'pane': {'x': 0, 'y': 0, 'w': 6, 'h': 2}},
        {'id': 'p2', 'title': 'second', 'traces': _panels()[0]['traces'], 'pane': {'x': 0, 'y': 2, 'w': 6, 'h': 2}},
    ]
    res = client.post('/api/export', json={'panels': panels, 'layout': {'width': 6, 'height': 4}})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_honors_ticks_inside(client):
    res = client.post('/api/export', json={'panels': _panels(), 'style': {'ticksInside': True}})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


# -- FFT panels -----------------------------------------------------------

def _fft_panels():
    return [{
        'id': 'p1', 'title': 'BR0SG0U1P0 (FFT)', 'kind': 'fft',
        'traces': [
            {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'aleDisp_y',
             'source': 'othd', 'kind': 'fft', 'color': '#dc2626'},
        ],
    }]


def test_export_renders_an_fft_panel(client):
    res = client.post('/api/export', json={'panels': _fft_panels()})
    assert res.status_code == 200
    assert res.mimetype == 'image/png'
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_fft_trace_values_matches_a_direct_computation(client):
    from src.web.api.export import _fft_trace_values, _trace_values
    from src.web.services.fft import compute_fft

    root = client.application.config['WORKSPACE_ROOT']
    trace = {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'source': 'othd'}
    values, times = _trace_values(root, trace)
    expected_freqs, expected_amplitude = compute_fft(times, values)

    freqs, amplitude = _fft_trace_values(root, trace)
    import numpy as np
    np.testing.assert_allclose(freqs, expected_freqs)
    np.testing.assert_allclose(amplitude, expected_amplitude)


def test_fft_trace_values_windows_to_t1_t2(client):
    import numpy as np
    from src.web.api.export import _fft_trace_values, _trace_values
    from src.web.services.fft import compute_fft

    root = client.application.config['WORKSPACE_ROOT']
    raw_values, raw_times = _trace_values(
        root, {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'source': 'othd'})
    t1, t2 = float(raw_times[5]), float(raw_times[15])
    mask = (raw_times >= t1) & (raw_times <= t2)
    expected_freqs, expected_amplitude = compute_fft(raw_times[mask], raw_values[mask])

    trace = {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'source': 'othd',
             't1': t1, 't2': t2}
    freqs, amplitude = _fft_trace_values(root, trace)
    np.testing.assert_allclose(freqs, expected_freqs)
    np.testing.assert_allclose(amplitude, expected_amplitude)


def test_fft_trace_values_returns_none_for_a_window_with_no_timesteps_in_it(client):
    from src.web.api.export import _fft_trace_values, _trace_values

    root = client.application.config['WORKSPACE_ROOT']
    _, raw_times = _trace_values(
        root, {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'source': 'othd'})
    past_the_end = float(raw_times[-1]) + 1000.0

    trace = {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'source': 'othd',
             't1': past_the_end}
    freqs, amplitude = _fft_trace_values(root, trace)
    assert freqs is None and amplitude is None


def test_fft_trace_values_reads_an_oisd_trace(client):
    from src.web.api.export import _fft_trace_values

    root = client.application.config['WORKSPACE_ROOT']
    trace = {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'totTrac_x', 'source': 'oisd'}
    freqs, amplitude = _fft_trace_values(root, trace)
    assert freqs is not None
    assert len(freqs) == len(amplitude) > 0


def test_fft_trace_values_returns_none_for_an_unregistered_case(client):
    from src.web.api.export import _fft_trace_values

    root = client.application.config['WORKSPACE_ROOT']
    trace = {'case': 'nope', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'source': 'othd'}
    freqs, amplitude = _fft_trace_values(root, trace)
    assert freqs is None and amplitude is None


def test_fft_trace_values_returns_none_for_non_uniform_sampling(client, monkeypatch):
    """The live /fft endpoint surfaces this as a visible 400 -- export.py's
    convention is to silently skip an unreadable trace instead, same as every
    other _*_trace_values helper here."""
    from src.web.api import export as export_mod
    from src.web.services import registry
    from src.web.services.loader import loader

    root = client.application.config['WORKSPACE_ROOT']
    case_dir = registry.case_path(root, 'BR0SG0U1P0')
    meta = loader.meta(case_dir, kind='othd')
    broken = meta.times.copy()
    broken[len(broken) // 2] += 10.0
    monkeypatch.setattr(meta, 'times', broken)

    trace = {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'source': 'othd'}
    freqs, amplitude = export_mod._fft_trace_values(root, trace)
    assert freqs is None and amplitude is None


def test_fft_auto_label_matches_plot_js_naming():
    from src.web.api.export import _fft_auto_label

    nodal = {'case': 'BR0SG0U1P0', 'row': 12, 'col': 'aleDisp_y', 'source': 'othd'}
    assert _fft_auto_label(nodal) == 'BR0SG0U1P0 r12 aleDisp_y FFT'

    surface = {'case': 'BR0SG0U1P0', 'block': 'cylinder_body', 'col': 'totTrac_x', 'source': 'oisd'}
    assert _fft_auto_label(surface) == 'BR0SG0U1P0 cylinder_body totTrac_x FFT'


def test_fft_auto_label_appends_the_window_when_windowed():
    from src.web.api.export import _fft_auto_label

    both = {'case': 'BR0SG0U1P0', 'row': 12, 'col': 'aleDisp_y', 'source': 'othd', 't1': 1.0, 't2': 2.0}
    assert _fft_auto_label(both) == 'BR0SG0U1P0 r12 aleDisp_y FFT [1.0, 2.0]'

    t1_only = {'case': 'BR0SG0U1P0', 'row': 12, 'col': 'aleDisp_y', 'source': 'othd', 't1': 1.0}
    assert _fft_auto_label(t1_only) == 'BR0SG0U1P0 r12 aleDisp_y FFT [1.0, end]'

    t2_only = {'case': 'BR0SG0U1P0', 'row': 12, 'col': 'aleDisp_y', 'source': 'othd', 't2': 2.0}
    assert _fft_auto_label(t2_only) == 'BR0SG0U1P0 r12 aleDisp_y FFT [start, 2.0]'


def test_export_fft_scales_a_trace_and_uses_its_custom_label(client, monkeypatch):
    import numpy as np
    from matplotlib.axes import Axes
    from src.web.api import export as export_mod

    root = client.application.config['WORKSPACE_ROOT']
    trace = {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'source': 'othd'}
    raw_freqs, raw_amplitude = export_mod._fft_trace_values(root, trace)

    captured = {}
    real_plot = Axes.plot

    def spy_plot(self, *args, **kwargs):
        captured['x'] = args[0]
        captured['y'] = args[1]
        captured['label'] = kwargs.get('label')
        return real_plot(self, *args, **kwargs)
    monkeypatch.setattr(Axes, 'plot', spy_plot)

    panels = _fft_panels()
    panels[0]['traces'][0]['scale'] = 2.0
    panels[0]['traces'][0]['label'] = 'Scaled spectrum'
    res = client.post('/api/export', json={'panels': panels})

    assert res.status_code == 200
    assert captured['label'] == 'Scaled spectrum'
    np.testing.assert_allclose(captured['x'], raw_freqs)
    np.testing.assert_allclose(captured['y'], raw_amplitude * 2.0)


def test_export_fft_xscale_normalizes_the_frequency_axis(client, monkeypatch):
    """xscale is independent of scale -- one normalizes frequency, the other
    the amplitude -- so both apply at once without interfering."""
    import numpy as np
    from matplotlib.axes import Axes
    from src.web.api import export as export_mod

    root = client.application.config['WORKSPACE_ROOT']
    trace = {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'source': 'othd'}
    raw_freqs, raw_amplitude = export_mod._fft_trace_values(root, trace)

    captured = {}
    real_plot = Axes.plot

    def spy_plot(self, *args, **kwargs):
        captured['x'] = args[0]
        captured['y'] = args[1]
        return real_plot(self, *args, **kwargs)
    monkeypatch.setattr(Axes, 'plot', spy_plot)

    panels = _fft_panels()
    panels[0]['traces'][0]['xscale'] = 0.5
    panels[0]['traces'][0]['scale'] = 2.0
    res = client.post('/api/export', json={'panels': panels})

    assert res.status_code == 200
    np.testing.assert_allclose(captured['x'], raw_freqs * 0.5)
    np.testing.assert_allclose(captured['y'], raw_amplitude * 2.0)


def test_xscale_of_defaults_to_1_when_unset():
    from src.web.api.export import _xscale_of
    assert _xscale_of({}) == 1


def test_xscale_of_treats_an_explicit_zero_as_real_not_unset():
    from src.web.api.export import _xscale_of
    assert _xscale_of({'xscale': 0}) == 0


def test_xscale_of_returns_the_explicit_value():
    from src.web.api.export import _xscale_of
    assert _xscale_of({'xscale': 0.5}) == 0.5


def test_export_fft_panel_with_no_readable_traces_does_not_crash(client):
    panels = [{
        'id': 'p1', 'title': 'FFT', 'kind': 'fft',
        'traces': [{'case': 'nope', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'source': 'othd'}],
    }]
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_fft_windowed_trace_matches_a_direct_windowed_computation(client, monkeypatch):
    import numpy as np
    from matplotlib.axes import Axes
    from src.web.api import export as export_mod

    root = client.application.config['WORKSPACE_ROOT']
    raw_values, raw_times = export_mod._trace_values(
        root, {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'source': 'othd'})
    t1, t2 = float(raw_times[5]), float(raw_times[15])

    captured = {}
    real_plot = Axes.plot

    def spy_plot(self, *args, **kwargs):
        captured['x'] = args[0]
        captured['label'] = kwargs.get('label')
        return real_plot(self, *args, **kwargs)
    monkeypatch.setattr(Axes, 'plot', spy_plot)

    trace = {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'source': 'othd',
             't1': t1, 't2': t2, 'color': '#dc2626'}
    panels = [{'id': 'p1', 'title': 'FFT', 'kind': 'fft', 'traces': [trace]}]
    res = client.post('/api/export', json={'panels': panels})

    expected_freqs, _ = export_mod._fft_trace_values(root, trace)
    assert res.status_code == 200
    np.testing.assert_allclose(captured['x'], expected_freqs)
    assert captured['label'] == f'BR0SG0U1P0 r0 aleDisp_y FFT [{t1}, {t2}]'
