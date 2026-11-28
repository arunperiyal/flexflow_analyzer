"""The delete stage end to end, on the dummy cases (tools/make_dummy.py): case13 (every rule
applies), case14 (a copy that differs), case15 (.out newer than the PLTs, as after a restart),
and the cases that must not lose anything (queued restart, post in flight, needs you)."""

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.commands.auto.apply import execute_apply
from src.core.transfer.ledger import Ledger

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def dummy(tmp_path, monkeypatch):
    root = tmp_path / 'dummy'
    subprocess.run([sys.executable, str(REPO / 'tools' / 'make_dummy.py'), '--root', str(root)],
                   check=True, capture_output=True)
    monkeypatch.setenv('PATH', f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv('FAKE_SLURM_DIR', str(root / 'slurm'))
    monkeypatch.chdir(root / 'bare')
    return root


def delete(case, **kw):
    args = SimpleNamespace(case=case, remote='local', only='delete', dry_run=False, yes=True,
                           delete=False)
    for k, v in kw.items():
        setattr(args, k, v)
    return execute_apply(args)


def files(dummy, case):
    return {p.relative_to(dummy / 'bare' / case).as_posix()
            for p in (dummy / 'bare' / case).rglob('*') if p.is_file()}


def kinds(names, step):
    """The files of one step: ascii, binary, out, rst."""
    return {n for n in names if f'.{step}.plt' in n or f'.{step}_' in n}


def cloud_files(dummy, case):
    return {p.relative_to(dummy / 'cloud' / 'bare' / case).as_posix()
            for p in (dummy / 'cloud' / 'bare' / case).rglob('*') if p.is_file()}


def test_case13_every_rule_applies_and_the_remote_is_untouched(dummy):
    before, remote = files(dummy, 'case13'), cloud_files(dummy, 'case13')
    assert delete('case13') == 0
    gone = before - files(dummy, 'case13')
    steps = range(800, 1001, 50)
    for t in steps:
        assert {f'RUN_1/riser.{t}.plt', f'binary/riser.{t}.plt',
                *(f'RUN_1/riser.{t}_{k}.out' for k in range(4))} <= gone
    assert {f'RUN_1/riser.750_{k}.rst' for k in range(4)} <= gone      # off the keep_rst grid
    assert not any(n.endswith('.rst') and ('.800_' in n or '.1000_' in n) for n in gone)
    assert cloud_files(dummy, 'case13') == remote
    entry = Ledger(dummy / 'bare').get('local', 'case13', 'binary/riser.900.plt')
    assert entry['deleted'] and entry['verified'] == 'md5' and entry['mtime']
    status = (dummy / 'bare' / 'case13' / '.casestatus.md').read_text()
    assert 'case organise out deleted:' in status and 'case organise plt deleted:' in status


def test_case13_a_second_run_finds_nothing_more(dummy, capsys):
    delete('case13')
    capsys.readouterr()
    assert delete('case13', dry_run=True) == 0
    assert 'nothing to do' in capsys.readouterr().out


def test_case14_a_copy_that_differs_holds_the_whole_case_and_needs_you(dummy):
    """The dry run that makes the question's totals finds the copy with another md5 and
    records it; the plan made right before the stage then holds the case: nothing goes."""
    before = files(dummy, 'case14')
    assert delete('case14') == 0
    assert files(dummy, 'case14') == before
    assert Ledger(dummy / 'bare').get('local', 'case14', 'binary/riser.900.plt')['mismatch']
    from src.commands.auto.show import gather, resolve_cases
    (snap, plan), = gather(resolve_cases('case14', dummy / 'bare'), 'local')[0]
    assert plan.needs_you and 'md5' in [i.text for i in plan.items if i.kind == 'needs'][0]
    assert not plan.ctx['delete_allowed']


def test_case15_an_out_newer_than_its_plt_stays_the_plt_goes(dummy):
    before = files(dummy, 'case15')
    assert delete('case15') == 0
    after = files(dummy, 'case15')
    for t in range(800, 1001, 50):
        assert f'binary/riser.{t}.plt' not in after                # its copy is checked
        assert f'RUN_1/riser.{t}.plt' in after                     # written after it: a restart
        assert all(f'RUN_1/riser.{t}_{k}.out' in after for k in range(4))


@pytest.mark.parametrize('case', ['case3', 'case4', 'case6', 'case11'])
def test_the_cases_that_must_not_lose_files_lose_none_but_thinned_sets(dummy, case):
    # case3: a queued restart; case4: a post job in flight; case6, case11: need you
    before = files(dummy, case)
    delete(case)
    lost = before - files(dummy, case)
    assert not [n for n in lost if not n.endswith('.rst')]
    if case in ('case4', 'case6', 'case11'):
        assert not lost                                            # held: not even a restart set


def test_case3_keeps_the_restart_point_and_what_the_queued_job_computes_again(dummy):
    before = files(dummy, 'case3')
    delete('case3')
    after = files(dummy, 'case3')
    assert {f'RUN_1/riser.700_{k}.rst' for k in range(4)} <= after     # restartTsId
    assert {f'RUN_1/riser.750_{k}.rst' for k in range(4)} <= after     # above it: provisional
    assert 'binary/riser.750.plt' in after


def test_the_restart_sets_that_stay_are_the_grid_the_newest_and_the_restart_point(dummy):
    delete('case13')
    names = {n for n in files(dummy, 'case13') if n.endswith('.rst')}
    assert {int(n.split('.')[1].split('_')[0]) for n in names} == {200, 400, 600, 800, 1000}
