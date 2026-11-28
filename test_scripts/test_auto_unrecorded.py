"""auto plans no .out deletion on a PLT that is only on the remote with no record of a
check: `case organise out` would keep it. It says so and names the --adopt command."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.commands.auto.show import gather, resolve_cases
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


def plan_of(dummy, case='case13'):
    (snap, plan), = gather(resolve_cases(case, dummy / 'bare'), 'local')[0]
    return plan


def only_on_remote(dummy, steps, case='case13', forget=True):
    """The PLT of these steps is gone here (and its ASCII); the remote keeps its copy."""
    root = dummy / 'bare' / case
    for t in steps:
        (root / 'binary' / f'riser.{t}.plt').unlink(missing_ok=True)
        (root / 'RUN_1' / f'riser.{t}.plt').unlink(missing_ok=True)
        if forget:
            Ledger(dummy / 'bare').forget('local', case, f'binary/riser.{t}.plt')


def test_a_remote_copy_with_no_record_is_not_planned_for_deletion(dummy):
    base = plan_of(dummy)
    assert 900 in base.ctx['del_out']                       # as it stands, it is planned
    only_on_remote(dummy, (900, 950))
    plan = plan_of(dummy)
    assert 900 not in plan.ctx['del_out'] and 950 not in plan.ctx['del_out']
    assert {800, 850, 1000} <= set(plan.ctx['del_out'])
    text = [i.text for i in plan.items if i.kind == 'needs' and 'nothing records' in i.text]
    assert len(text) == 1
    assert '--adopt --t1 900 --t2 950' in text[0] and '--remote local' in text[0]
    assert plan.needs_you
    # and no delete command spans the steps it left out
    cmds = [s.command for s in plan.steps if s.key == 'delete-out']
    assert not any(f'--t1 {a}' in c for c in cmds for a in (900, 950))


def test_a_recorded_copy_is_planned_again(dummy):
    only_on_remote(dummy, (900,))
    assert [i for i in plan_of(dummy).items if 'nothing records' in i.text]
    there = dummy / 'cloud' / 'bare' / 'case13' / 'binary' / 'riser.900.plt'
    import hashlib
    for how in ('md5', 'adopted'):
        Ledger(dummy / 'bare').record('local', 'case13', 'binary/riser.900.plt',
                                      size=there.stat().st_size, mtime=there.stat().st_mtime,
                                      md5=hashlib.md5(there.read_bytes()).hexdigest(),
                                      verified=how, path=str(there))
        plan = plan_of(dummy)
        assert 900 in plan.ctx['del_out'], how
        assert not [i for i in plan.items if 'nothing records' in i.text], how


def test_a_local_plt_is_never_called_unrecorded(dummy):
    Ledger(dummy / 'bare').forget('local', 'case13', 'binary/riser.900.plt')
    plan = plan_of(dummy)
    assert not [i for i in plan.items if 'nothing records' in i.text]
