"""auto log: read back the logs `auto apply` writes in <folder>/auto_logs/."""

import argparse
from pathlib import Path

import pytest

from src.commands.auto.log import case_name, execute_log, logs_folder
from src.core.auto.runlog import (RunLog, is_failure, list_logs, read_log, started_at,
                                  summarise)


def write_run(folder, stamp, lines, end=True):
    """A log written by RunLog itself, named for the moment `stamp` (YYYY-MM-DD_HHMMSS)."""
    log = RunLog(folder, stamp)
    log.line('', 'start', 'auto apply all --remote cloud --only history,upload for 2 case(s)')
    for case, kind, text in lines:
        log.line(case, kind, text)
    if end:
        log.line('', 'end', '1 step(s) failed; 0 case(s) need you')
    log.close()
    return log.path


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_run(tmp_path, '2026-11-17_090000', [('C1', 'upload', 'ok: sent 3 files'),
                                              ('C2', 'post', 'ok: run post full')])
    write_run(tmp_path, '2026-11-18_113000', [('C1', 'upload', 'ok: sent 12 files'),
                                              ('C2', 'post', 'FAILED: sbatch refused'),
                                              ('C2', 'post', 'sbatch: error: no account'),
                                              ('C2', 'problem', 'remote not reachable')])
    return tmp_path


def args(**kw):
    base = dict(case=None, list=False, log=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_logs_are_listed_newest_first_and_read_back(folder):
    logs = list_logs(folder)
    assert [p.name for p in logs] == ['auto_2026-11-18_113000.log', 'auto_2026-11-17_090000.log']
    assert started_at(logs[0]).strftime('%Y-%m-%d %H:%M') == '2026-11-18 11:30'
    entries = read_log(logs[0])
    assert entries[0].kind == 'start' and entries[0].case == ''
    assert (entries[1].case, entries[1].kind, entries[1].text) == ('C1', 'upload', 'ok: sent 12 files')
    assert entries[-1].kind == 'end'
    assert [is_failure(e) for e in entries[1:-1]] == [False, True, False, True]


def test_the_summary_of_a_run(folder):
    info = summarise(read_log(list_logs(folder)[0]))
    assert info['cases'] == ['C1', 'C2'] and info['steps'] == 2 and info['failed'] == 2
    assert info['start'].startswith('auto apply all') and info['end'].startswith('1 step(s) failed')


def test_a_run_with_no_end_line_says_so(folder, capsys):
    write_run(folder, '2026-11-19_080000', [('C1', 'upload', 'ok: sent 1 file')], end=False)
    assert summarise(read_log(list_logs(folder)[0]))['end'] is None
    execute_log(args(list=True))
    assert 'no end line' in capsys.readouterr().out


def test_auto_log_shows_the_newest_run_and_fails_when_a_step_did(folder, capsys):
    status = execute_log(args())
    out = capsys.readouterr().out
    assert status == 1
    assert 'auto_2026-11-18_113000.log' in out and 'sent 12 files' in out
    assert 'FAILED: sbatch refused' in out and 'sbatch: error: no account' in out
    assert 'sent 3 files' not in out                      # the older run
    assert '2 failed' in out and 'run 1 of 2' in out


def test_a_case_keeps_its_lines_and_the_runs_own(folder, capsys):
    execute_log(args(case='C1'))
    out = capsys.readouterr().out
    assert 'sent 12 files' in out and 'sbatch' not in out
    assert 'auto apply all' in out                        # start and end stay
    # a path names the case by its last part
    assert case_name('/scratch/x/C1') == 'C1' and case_name('*') == '' and case_name(None) == ''


def test_a_case_the_run_left_alone_is_said(folder, capsys):
    status = execute_log(args(case='C9'))
    assert status == 0 and 'did nothing for C9' in capsys.readouterr().out


def test_log_n_reads_an_older_run_and_n_out_of_range_is_an_error(folder, capsys):
    assert execute_log(args(log=2)) == 0
    out = capsys.readouterr().out
    assert 'sent 3 files' in out and 'run 2 of 2' in out
    assert execute_log(args(log=3)) == 2
    assert 'out of range' in capsys.readouterr().out


def test_list_has_one_line_per_run(folder, capsys):
    assert execute_log(args(list=True)) == 0
    out = capsys.readouterr().out
    assert '2026-11-18 11:30' in out and '2026-11-17 09:00' in out
    assert 'auto apply all --remote cloud' in out and '2 run(s)' in out


def test_no_logs_is_not_an_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert execute_log(args()) == 0
    assert 'No auto logs' in capsys.readouterr().out


def test_from_inside_a_case_the_folder_above_is_read(folder, monkeypatch, capsys):
    case = folder / 'C1'
    case.mkdir()
    monkeypatch.chdir(case)
    assert logs_folder(Path.cwd()) == folder
    execute_log(args(case='C1'))
    assert 'sent 12 files' in capsys.readouterr().out
