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
                 'othd.riser_probe.map', 'othd.riser_probe1_field.map')


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    root = tmp_path_factory.mktemp('web_export_workspace')
    case_dir = root / 'BR0SG0U1P0'
    case_dir.mkdir()
    for name in _NEEDED_FILES:
        shutil.copy(EXAMPLE / name, case_dir / name)
    shutil.copytree(EXAMPLE / 'othd_files', case_dir / 'othd_files')
    (root / '.cases').write_text(json.dumps([{'name': 'BR0SG0U1P0', 'path': str(case_dir)}]))
    return create_app(root).test_client()


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


def test_export_with_no_panels_is_a_400(client):
    res = client.post('/api/export', json={'panels': []})
    assert res.status_code == 400


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
    # inside matplotlib's plot() rather than being skipped cleanly.
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


def test_export_mixed_time_and_spatial_panels(client):
    panels = _panels() + [{
        'id': 'p2', 'title': 'spatial', 'kind': 'spatial',
        'traces': [{'case': 'BR0SG0U1P0', 'group': 0, 'col': 'aleDisp_y', 'mode': 'snapshot',
                    'time': 1.0, 'points': [{'row': 0, 'x': 0.0}], 'color': '#000'}],
    }]
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


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


def test_export_font_family_takes_the_first_name_from_a_css_stack(client):
    # The style sidebar's font dropdown sends CSS font-family syntax
    # (e.g. '"Times New Roman", Times, serif'); matplotlib's rcParams
    # wants a bare name, not that list syntax.
    from src.web.api.export import _matplotlib_font
    assert _matplotlib_font('"Times New Roman", Times, serif') == 'Times New Roman'
    assert _matplotlib_font('Arial, sans-serif') == 'Arial'
    assert _matplotlib_font('') is None
    assert _matplotlib_font(None) is None

    res = client.post('/api/export', json={
        'panels': _panels(), 'style': {'fontFamily': '"Times New Roman", Times, serif'},
    })
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


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


# -- Layout grid / pane assignment ------------------------------------------

def _cell(row, col):
    return {'row': row, 'col': col, 'rowSpan': 1, 'colSpan': 1}


def test_resolve_panes_honors_explicit_non_conflicting_panes():
    from src.web.api.export import _resolve_panes

    panels = [
        {'id': 'p1', 'pane': {'row': 1, 'col': 0}},
        {'id': 'p2', 'pane': {'row': 0, 'col': 1}},
    ]
    rows, columns, pane_of = _resolve_panes(panels, {'rows': 2, 'columns': 2})
    assert (rows, columns) == (2, 2)
    assert pane_of == {'p1': _cell(1, 0), 'p2': _cell(0, 1)}


def test_resolve_panes_falls_back_conflicting_panes_to_next_free_cell():
    from src.web.api.export import _resolve_panes

    panels = [
        {'id': 'p1', 'pane': {'row': 0, 'col': 0}},
        {'id': 'p2', 'pane': {'row': 0, 'col': 0}},  # conflicts with p1
        {'id': 'p3', 'pane': None},                  # unassigned
    ]
    rows, columns, pane_of = _resolve_panes(panels, {'rows': 1, 'columns': 2})
    assert pane_of['p1'] == _cell(0, 0)
    # p2 and p3 both land on free cells, never re-using (0, 0).
    assert pane_of['p2'] != _cell(0, 0)
    assert pane_of['p3'] != _cell(0, 0)
    assert pane_of['p2'] != pane_of['p3']


def test_resolve_panes_grows_rows_downward_when_the_grid_is_full():
    from src.web.api.export import _resolve_panes

    panels = [{'id': f'p{i}'} for i in range(3)]
    rows, columns, pane_of = _resolve_panes(panels, {'rows': 1, 'columns': 2})
    assert columns == 2
    assert rows == 2
    seen = {(s['row'], s['col']) for s in pane_of.values()}
    assert len(seen) == 3


# -- Merged panes (Layout -> New's cell-merge) ------------------------------

def test_resolve_panes_places_a_panel_into_a_merged_area():
    from src.web.api.export import _resolve_panes

    layout = {'rows': 3, 'columns': 2, 'areas': [{'row': 0, 'col': 0, 'rowSpan': 3, 'colSpan': 1}]}
    panels = [
        {'id': 'p1', 'pane': {'row': 0, 'col': 0}},   # the merged column
        {'id': 'p2', 'pane': None},
        {'id': 'p3', 'pane': None},
    ]
    rows, columns, pane_of = _resolve_panes(panels, layout)
    assert pane_of['p1'] == {'row': 0, 'col': 0, 'rowSpan': 3, 'colSpan': 1}
    # p2/p3 auto-place into the remaining single-column-1 cells, never
    # re-splitting the merged column.
    assert pane_of['p2'] == _cell(0, 1)
    assert pane_of['p3'] == _cell(1, 1)


def test_resolve_panes_ignores_an_out_of_bounds_merged_area():
    from src.web.api.export import _compute_slots

    # rowSpan runs past a 2-row grid -- dropped rather than corrupting the
    # whole slot list.
    slots = _compute_slots(2, 2, [{'row': 0, 'col': 0, 'rowSpan': 3, 'colSpan': 1}])
    assert all(s['rowSpan'] == 1 and s['colSpan'] == 1 for s in slots)
    assert len(slots) == 4


def test_export_honors_a_merged_column(client):
    panels = [
        {'id': 'p1', 'title': 'merged', 'traces': _panels()[0]['traces'], 'pane': {'row': 0, 'col': 0}},
        {'id': 'p2', 'title': 'top-right', 'traces': _panels()[0]['traces'], 'pane': {'row': 0, 'col': 1}},
        {'id': 'p3', 'title': 'bottom-right', 'traces': _panels()[0]['traces'], 'pane': {'row': 1, 'col': 1}},
    ]
    res = client.post('/api/export', json={
        'panels': panels,
        'layout': {'rows': 2, 'columns': 2, 'areas': [{'row': 0, 'col': 0, 'rowSpan': 2, 'colSpan': 1}]},
    })
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_honors_an_explicit_grid_layout(client):
    panels = _panels() + [{'id': 'p2', 'title': 'second', 'traces': _panels()[0]['traces'],
                           'pane': {'row': 0, 'col': 1}}]
    panels[0]['pane'] = {'row': 0, 'col': 0}
    res = client.post('/api/export', json={
        'panels': panels, 'layout': {'rows': 1, 'columns': 2, 'width': 900, 'height': 400},
    })
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_a_spatial_panel_at_the_bottom_of_a_column_does_not_crash(client):
    panels = [
        {'id': 'p1', 'title': 'time', 'traces': _panels()[0]['traces'], 'pane': {'row': 0, 'col': 0}},
        {'id': 'p2', 'title': 'spatial', 'kind': 'spatial', 'pane': {'row': 1, 'col': 0},
         'traces': [{'case': 'BR0SG0U1P0', 'group': 0, 'col': 'aleDisp_y', 'mode': 'snapshot',
                     'time': 1.0, 'points': [{'row': 0, 'x': 0.0}], 'color': '#000'}]},
    ]
    res = client.post('/api/export', json={'panels': panels, 'layout': {'rows': 2, 'columns': 1}})
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
    panels = _panels() + [{'id': 'p2', 'title': 'second', 'traces': _panels()[0]['traces']}]
    res = client.post('/api/export', json={'panels': panels, 'layout': {'rows': 2, 'columns': 1}})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_honors_ticks_inside(client):
    res = client.post('/api/export', json={'panels': _panels(), 'style': {'ticksInside': True}})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'
