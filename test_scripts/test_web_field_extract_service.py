"""Unit tests for services/field_extract.py's resolve_steps -- pure step-range
logic that only needs PLT *filenames* to exist (list_steps globs the
directory), not real PLT content, so no example-case fixture is needed here.
The rest of the module (run_probe_extract, write_mesh_vtu) needs real PLT
data and is covered by test_web_field_extract.py instead.
"""

from src.web.services.field_extract import resolve_steps


def _touch_plt_files(tmp_path, problem, steps):
    binary_dir = tmp_path / 'binary'
    binary_dir.mkdir()
    for s in steps:
        (binary_dir / f'{problem}.{s}.plt').touch()
    return binary_dir


def test_single_timestep(tmp_path):
    binary_dir = _touch_plt_files(tmp_path, 'riser', [100, 200, 300])
    assert resolve_steps(binary_dir, 'riser', timestep=200) == [200]


def test_t1_t2_range_returns_existing_steps_within_it(tmp_path):
    binary_dir = _touch_plt_files(tmp_path, 'riser', [100, 200, 300, 400])
    assert resolve_steps(binary_dir, 'riser', t1=150, t2=350) == [200, 300]


def test_t1_t2_range_is_order_independent(tmp_path):
    binary_dir = _touch_plt_files(tmp_path, 'riser', [100, 200, 300])
    assert resolve_steps(binary_dir, 'riser', t1=300, t2=100) == [100, 200, 300]


def test_t1_only_is_treated_as_a_single_timestep(tmp_path):
    binary_dir = _touch_plt_files(tmp_path, 'riser', [100, 200])
    assert resolve_steps(binary_dir, 'riser', t1=100) == [100]


def test_t2_only_is_treated_as_a_single_timestep(tmp_path):
    binary_dir = _touch_plt_files(tmp_path, 'riser', [100, 200])
    assert resolve_steps(binary_dir, 'riser', t2=200) == [200]


def test_nothing_given_returns_none(tmp_path):
    binary_dir = _touch_plt_files(tmp_path, 'riser', [100])
    assert resolve_steps(binary_dir, 'riser') is None


def test_range_with_no_matching_steps_returns_an_empty_list(tmp_path):
    binary_dir = _touch_plt_files(tmp_path, 'riser', [100, 200])
    assert resolve_steps(binary_dir, 'riser', t1=1000, t2=2000) == []
