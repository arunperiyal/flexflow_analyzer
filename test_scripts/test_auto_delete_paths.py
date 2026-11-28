"""`auto apply --delete` runs the commands `auto show` lists (auto.md 13.27), so on the same
dummy case it must leave the same files as those commands run by hand. Each command runs in
its own process, as a user runs it. (case14 had a copy with another md5: the commands deleted
the ASCII PLT of that step; the chain now keeps everything on it, as `apply` always did.)"""

import io
import os
import shlex
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from src.commands.auto.apply import execute_apply
from src.commands.auto.show import gather, resolve_cases

REPO = Path(__file__).resolve().parent.parent

# case14 is left out: the dry run `apply` makes first records the copy with another md5, which
# holds the case before anything is deleted (test_auto_delete_cases); a hand run has no such pass
CASES = ['case13', 'case15', 'case3', 'case4', 'case6', 'case11']


@pytest.fixture
def dummy(tmp_path, monkeypatch):
    root = tmp_path / 'dummy'
    subprocess.run([sys.executable, str(REPO / 'tools' / 'make_dummy.py'), '--root', str(root)],
                   check=True, capture_output=True)
    monkeypatch.setenv('PATH', f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv('FAKE_SLURM_DIR', str(root / 'slurm'))
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))      # the shell keeps state under ~/.flexflow
    (tmp_path / 'home').mkdir()
    monkeypatch.chdir(root / 'bare')
    return root


def files(dummy, case):
    return {p.relative_to(dummy / 'bare' / case).as_posix()
            for p in (dummy / 'bare' / case).rglob('*')
            if p.is_file() and p.name not in ('.casestatus.md',)}


def by_apply(dummy, case):
    args = SimpleNamespace(case=case, remote='local', only='delete', dry_run=False, yes=True,
                           delete=False)
    execute_apply(args)


def by_commands(dummy, case):
    """What `auto show` lists as delete steps, run as the commands they are, each in its
    own process (the in-process shell keeps state between runs)."""
    (snap, plan), = gather(resolve_cases(case, dummy / 'bare'), 'local')[0]
    ran = []
    for step in plan.steps:
        if step.kind == 'delete' and not plan.ctx.get('delete_hold'):
            subprocess.run([sys.executable, str(REPO / 'main.py'), *shlex.split(step.command), '--yes'],
                           cwd=dummy / 'bare', check=False, capture_output=True,
                           env={**os.environ, 'HOME': str(dummy.parent / 'home')})
            ran.append(step.command)
    return ran


@pytest.mark.parametrize('case', CASES)
def test_both_paths_leave_the_same_files(dummy, case, tmp_path, monkeypatch):
    twin = tmp_path / 'twin'
    subprocess.run([sys.executable, str(REPO / 'tools' / 'make_dummy.py'), '--root', str(twin)],
                   check=True, capture_output=True)
    before = files(dummy, case)

    by_apply(dummy, case)
    kept_by_apply = files(dummy, case)

    monkeypatch.setenv('PATH', f"{twin / 'bin'}{os.pathsep}{os.environ['PATH'].split(os.pathsep, 1)[1]}")
    monkeypatch.setenv('FAKE_SLURM_DIR', str(twin / 'slurm'))
    monkeypatch.chdir(twin / 'bare')
    by_commands(twin, case)
    kept_by_commands = files(twin, case)

    only_apply = sorted(before - kept_by_apply - (before - kept_by_commands))
    only_commands = sorted((before - kept_by_commands) - (before - kept_by_apply))
    assert not only_apply and not only_commands, (case, only_apply, only_commands)

