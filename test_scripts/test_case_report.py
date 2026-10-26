"""`case report`: the last step of each case, read from the end of its .othd
files rather than parsing them whole."""

from pathlib import Path

from src.commands.case.report_impl import command as report


def othd(path, ts_ids, nodes=1):
    rows = ''.join(f"tsId {t}\ntime {t * 0.05}\n" + "0.1 0.2 0.3\n" * nodes for t in ts_ids)
    path.write_text("mask 455\nnOths 1\n" + rows)
    return path


def test_last_tsid_reads_the_tail(tmp_path):
    assert report._last_tsid(othd(tmp_path / 'a.othd', range(1, 5001))) == 5000
    # a restart inside the file: where the restarted run stopped
    assert report._last_tsid(othd(tmp_path / 'b.othd', [1, 2, 3, 4, 2, 3])) == 3
    assert report._last_tsid(othd(tmp_path / 'c.othd', [])) is None


def test_last_tsid_with_blocks_bigger_than_the_first_window(tmp_path):
    # ~1.2 MB per step: the first 1 MB window holds no tsId line at all
    assert report._last_tsid(othd(tmp_path / 'wide.othd', [7, 8, 9], nodes=100_000)) == 9


def test_last_timestep_across_parts(tmp_path):
    othd(tmp_path / 'riser1.othd', range(1, 101))
    othd(tmp_path / 'riser2.othd', range(90, 151))
    othd(tmp_path / 'riser3.othd', range(20, 41))
    assert report._last_othd_timestep_in_dir(tmp_path) == 150
    assert report._last_othd_timestep_in_dir(tmp_path / 'nope') is None


# --- the .case_report cache ---------------------------------------------------

import argparse
import json

import pytest


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(report, '_refreshed', set())
    cases = []
    for name in ('C1', 'C2'):
        case = tmp_path / name
        (case / 'othd_files').mkdir(parents=True)
        (case / 'binary').mkdir()
        (case / 'simflow.config').write_text('problem = riser\ndir = ./RUN_1\n')
        othd(case / 'othd_files' / 'riser1.othd', range(1, 101))
        (case / 'binary' / 'riser.100.plt').write_text('x')
        cases.append({'name': name, 'path': str(case)})
    (tmp_path / '.cases').write_text(json.dumps(cases))
    return tmp_path


def run(project, capsys, **flags):
    args = argparse.Namespace(dir=str(project), run=False, size=False, update=False, help=False)
    for key, value in flags.items():
        setattr(args, key, value)
    report.execute_report(args)
    return capsys.readouterr().out


def lasts(text):
    """{case: [archive, binary, ...]} from the table (after the State column)."""
    rows = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip('│ ').split('│')]
        if cells and cells[0] in ('C1', 'C2'):
            rows[cells[0]] = cells[2:]
    return rows


def test_first_report_in_a_session_computes_then_reads_the_file(project, capsys):
    first = run(project, capsys)
    assert lasts(first)['C1'][:2] == ['100', '100'] and 'From .case_report' not in first
    saved = json.loads((project / '.case_report').read_text())
    assert saved['cases'][str(project / 'C1')]['archive']['value'] == 100

    # the case moves on; within the session the saved report is shown, and says so
    othd(project / 'C1' / 'othd_files' / 'riser2.othd', range(90, 201))
    second = run(project, capsys)
    assert lasts(second)['C1'][0] == '100'
    assert 'From .case_report, computed' in second and '--update' in second

    assert lasts(run(project, capsys, update=True))['C1'][0] == '200'


def test_a_new_session_recomputes(project, capsys):
    run(project, capsys)
    othd(project / 'C1' / 'othd_files' / 'riser2.othd', range(90, 201))
    report._refreshed.clear()                       # a new shell, or the plain CLI
    assert lasts(run(project, capsys))['C1'][0] == '200'


def test_a_column_not_cached_yet_is_computed_and_kept(project, capsys, monkeypatch):
    run(project, capsys)
    out = run(project, capsys, size=True)
    assert 'B' in lasts(out)['C1'][2]
    sizes = []
    monkeypatch.setattr(report, '_dir_size', lambda p: sizes.append(p) or 0)
    run(project, capsys, size=True)                 # now from the file
    assert sizes == []
    report._refreshed.clear()
    run(project, capsys)                            # a fresh report without --size ...
    run(project, capsys, size=True)                 # ... keeps the sizes
    assert sizes == []


def test_a_bad_or_missing_cache_is_rebuilt(project, capsys):
    run(project, capsys)
    (project / '.case_report').write_text('{"version": 1, "cases": {"x": 5, "%s": {"archive": 3}}}'
                                          % (project / 'C1'))
    assert lasts(run(project, capsys))['C1'][0] == '100'
    (project / '.case_report').write_text('not json')
    assert lasts(run(project, capsys))['C1'][0] == '100'
    assert 'x' not in json.loads((project / '.case_report').read_text())['cases']


def test_state_column_from_the_case_notes(project, capsys):
    from src.core import case_status
    case_status.ensure(project / 'C1')
    case_status.set_state(project / 'C1', 'running')
    states = {}
    for line in run(project, capsys).splitlines():
        cells = [c.strip() for c in line.strip('│ ').split('│')]
        if cells and cells[0] in ('C1', 'C2'):
            states[cells[0]] = cells[1]
    assert states == {'C1': 'running', 'C2': '—'}
