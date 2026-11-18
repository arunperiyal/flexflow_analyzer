"""`data stats --func maxloc|minloc|zeroloc` offers the PLT it chose, per case, to the
command after a `|` (shellkit rows): `data stats ... | case download plt`."""

import io
from types import SimpleNamespace

import pytest
from rich.console import Console

from src.commands.data.stats_impl.command import execute_statistics
from test_data_commands import args, case, registry  # noqa: F401  (fixtures)


@pytest.fixture
def offered(monkeypatch):
    rows = []
    monkeypatch.setattr('shellkit.current_runtime',
                        lambda: SimpleNamespace(emit=lambda r: rows.extend(r)))
    return rows


def test_maxloc_offers_the_plt_it_chose_for_each_case(registry, offered):
    execute_statistics(args(case="*", var=["aleDisp_x"], func=["maxloc"], freq=1))
    cases = [r['case'].rsplit('/', 1)[-1] for r in offered]
    assert cases == ['Good1', 'Good2']
    assert all(r['time'] and int(r['time']) >= 1 for r in offered)


def test_a_function_that_names_no_plt_offers_nothing(registry, offered):
    execute_statistics(args(case="*", var=["aleDisp_x"], func=["max"]))
    assert offered == []


def test_zeroloc_offers_both_directions(case, offered):
    execute_statistics(args(case=str(case), var=["aleDisp_x"], func=["zeroloc"], freq=1))
    assert len(offered) == 2 and {r['case'] for r in offered} == {str(case)}


def test_without_a_shell_nothing_is_needed(registry, monkeypatch):
    monkeypatch.setattr('shellkit.current_runtime', lambda: None)
    execute_statistics(args(case="*", var=["aleDisp_x"], func=["maxloc"], freq=1))


def test_an_older_shellkit_without_rows_still_gives_the_table(registry, monkeypatch, capsys):
    monkeypatch.setattr('shellkit.current_runtime', lambda: SimpleNamespace())   # no emit
    execute_statistics(args(case="*", var=["aleDisp_x"], func=["maxloc"], freq=1))
    assert 'maxloc' in capsys.readouterr().out


def test_piped_into_a_command_it_runs_per_case_at_that_step(registry, monkeypatch, tmp_path):
    from shellkit import Runtime
    from src.cli.app import create_app
    import shellkit.runtime
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    monkeypatch.setattr(shellkit.runtime, '_current', shellkit.runtime._current)
    out = io.StringIO()
    rt = Runtime(create_app(), console=Console(file=out, width=200, color_system=None),
                 err_console=Console(file=io.StringIO(), width=200, color_system=None))
    status = rt.execute_line('use freq:1; data stats * --var aleDisp_x --func maxloc | case show')
    text = out.getvalue()
    assert status == 0, text
    assert '── 1/2  case:Good1 time:' in text and '── 2/2  case:Good2 time:' in text
    assert text.count('Using case: ') == 2             # each run had its case from the row
