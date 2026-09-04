"""Tests for `case add` and the .cases registry it writes.

Pins the CLI's existing table + prompt output before splitting the pure
scan/write parts out of execute_add() for reuse by the web layer.
"""

import argparse
import json

import pytest

from src.commands.case.add_impl.command import execute_add, load_cases_file


@pytest.fixture
def workspace(tmp_path):
    for name in ("caseA", "caseB", "not_a_case"):
        d = tmp_path / name
        d.mkdir()
        if name != "not_a_case":
            (d / "simflow.config").write_text('problem = "p"\n')
    return tmp_path


def _args(**kw):
    ns = argparse.Namespace(help=False, dir=None)
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def test_add_all_writes_cases_file(workspace, monkeypatch, capsys):
    monkeypatch.setattr('builtins.input', lambda: '')
    execute_add(_args(dir=str(workspace)))

    out = capsys.readouterr().out
    assert 'Scanning:' in out
    assert 'caseA' in out and 'caseB' in out
    assert 'not_a_case' not in out
    assert 'Found 2 case(s).' in out
    assert 'Wrote 2 case(s)' in out

    entries = load_cases_file(workspace)
    names = sorted(e['name'] for e in entries)
    assert names == ['caseA', 'caseB']
    for e in entries:
        assert e['path'] == str(workspace / e['name'])


def test_add_with_exclusion(workspace, monkeypatch, capsys):
    monkeypatch.setattr('builtins.input', lambda: '1')
    execute_add(_args(dir=str(workspace)))

    out = capsys.readouterr().out
    assert 'Excluded 1 case(s).' in out

    entries = load_cases_file(workspace)
    assert len(entries) == 1


def test_add_no_cases_found(tmp_path, monkeypatch, capsys):
    execute_add(_args(dir=str(tmp_path)))
    out = capsys.readouterr().out
    assert 'No case directories found' in out
    assert not (tmp_path / '.cases').exists()
