"""Basic shell commands, so the shell need not be left for them: find, mkdir,
mv, touch, top. They work on the shell's cwd and pipe like ls and grep."""

import io
import os
import subprocess

import pytest
from rich.console import Console

from shellkit import Runtime


@pytest.fixture
def rt(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    work = tmp_path / 'work'
    (work / 'CaseA' / 'RUN_1').mkdir(parents=True)
    (work / 'CaseA' / 'simflow.config').write_text('')
    (work / 'CaseA' / 'riser.othd').write_text('')
    (work / 'notes').mkdir()
    (work / 'notes' / 'Riser_notes.txt').write_text('')
    (work / '.git').mkdir()
    (work / '.git' / 'riser.othd').write_text('')
    monkeypatch.chdir(work)
    from src.cli.app import create_app
    runtime = Runtime(create_app(),
                      console=Console(file=io.StringIO(), width=200, color_system=None),
                      err_console=Console(file=io.StringIO(), width=200, color_system=None))
    runtime.work = work
    return runtime


def out(rt):
    text = rt.console.file.getvalue()
    rt.console.file.seek(0)
    rt.console.file.truncate()
    return text


def err(rt):
    return rt.err_console.file.getvalue()


def piped(rt, line):
    """Lines a command sends down a pipe (`line | cat`)."""
    out(rt)
    assert rt.execute_line(f'{line} | cat') == 0, err(rt)
    return out(rt).splitlines()


# --- find -----------------------------------------------------------------------

def test_find_any_file_or_directory_by_substring_ignoring_case(rt):
    assert piped(rt, 'find riser') == ['CaseA/riser.othd', 'notes/Riser_notes.txt']


def test_find_glob_type_filters_and_path(rt):
    assert piped(rt, 'find *.othd') == ['CaseA/riser.othd']
    assert piped(rt, 'find -d run') == ['CaseA/RUN_1/']
    assert piped(rt, 'find -f othd') == ['CaseA/riser.othd']
    assert piped(rt, 'find -c') == ['CaseA/']
    assert piped(rt, 'find * notes') == ['notes/Riser_notes.txt']


def test_find_with_nothing_found_reports_it(rt):
    assert rt.execute_line('find nothing_like_this') == 1
    assert 'nothing matches' in err(rt)


def test_find_at_the_prompt_counts(rt):
    assert rt.execute_line('find othd') == 0
    text = out(rt)
    assert 'CaseA/riser.othd' in text and '1 found' in text


# --- mkdir / touch / mv --------------------------------------------------------------

def test_mkdir_and_parents(rt):
    work = rt.work
    assert rt.execute_line('mkdir new') == 0
    assert (work / 'new').is_dir()
    assert rt.execute_line('mkdir new') == 1 and 'already exists' in err(rt)
    assert rt.execute_line('mkdir a/b/c') == 1 and 'use -p' in err(rt)
    assert rt.execute_line('mkdir -p a/b/c new') == 0
    assert (work / 'a' / 'b' / 'c').is_dir()


def test_touch_creates_and_updates(rt):
    path = rt.work / 'log.txt'
    assert rt.execute_line('touch log.txt') == 0 and path.exists()
    os.utime(path, (1, 1))
    assert rt.execute_line('touch log.txt') == 0
    assert path.stat().st_mtime > 1


def test_mv_renames_and_moves_into_a_directory(rt):
    work = rt.work
    (work / 'a.txt').write_text('a')
    (work / 'b.txt').write_text('b')
    assert rt.execute_line('mv a.txt c.txt') == 0
    assert (work / 'c.txt').read_text() == 'a' and not (work / 'a.txt').exists()
    assert rt.execute_line('mv *.txt notes') == 0
    assert sorted(p.name for p in (work / 'notes').iterdir()) == \
        ['Riser_notes.txt', 'b.txt', 'c.txt']
    assert rt.execute_line('mv notes CaseA') == 0
    assert (work / 'CaseA' / 'notes' / 'b.txt').exists()


def test_mv_asks_before_replacing(rt, monkeypatch):
    work = rt.work
    (work / 'a.txt').write_text('new')
    (work / 'b.txt').write_text('old')
    monkeypatch.setattr(rt, 'confirm', lambda q: False)
    assert rt.execute_line('mv a.txt b.txt') == 0
    assert (work / 'b.txt').read_text() == 'old' and (work / 'a.txt').exists()
    assert rt.execute_line('mv -f a.txt b.txt') == 0
    assert (work / 'b.txt').read_text() == 'new' and not (work / 'a.txt').exists()


def test_mv_needs_a_directory_for_several_sources(rt):
    (rt.work / 'a.txt').write_text('')
    (rt.work / 'b.txt').write_text('')
    assert rt.execute_line('mv a.txt b.txt c.txt') == 1
    assert 'existing directory' in err(rt)


# --- top -------------------------------------------------------------------------------

def test_top_runs_the_system_top(rt, monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, 'PID USER\n1 root\n', '')

    monkeypatch.setattr(subprocess, 'run', fake_run)
    monkeypatch.setenv('USER', 'arun')
    assert rt.execute_line('top -u $USER') == 0
    assert calls[-1] == ['top', '-u', 'arun']
    assert rt.run_captured('top').splitlines() == ['PID USER', '1 root']
    assert calls[-1] == ['top', '-b', '-n', '1']
