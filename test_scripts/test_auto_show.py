"""`auto show` on freshly built dummy cases (tools/make_dummy.py), with the fake
SLURM and the folder cloud: each case gets what dummy/README.md says."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.commands.auto.show import gather, resolve_cases
from src.core.auto.conf import AutoConfError

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def dummy(tmp_path, monkeypatch):
    root = tmp_path / 'dummy'
    subprocess.run([sys.executable, str(REPO / 'tools' / 'make_dummy.py'), '--root', str(root)],
                   check=True, capture_output=True)
    monkeypatch.setenv('PATH', f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv('FAKE_SLURM_DIR', str(root / 'slurm'))
    return root


def plans(dummy, case='*', base=None):
    results, confs, problems = gather(resolve_cases(case, base or dummy / 'bare'))
    return {snap.name: plan for snap, plan in results}, problems


def needs(plan):
    return [i.text for i in plan.items if i.kind == 'needs']


def test_every_case_gets_what_the_readme_says(dummy):
    got, problems = plans(dummy)
    assert problems == []
    assert {n: p.post for n, p in got.items() if p.post} == {
        'case2': (450, 600, 'full'),      # running: up to the last settled step
        'case3': (550, 700, 'full'),      # queued restart from 700
        'case5': (350, 500, 'full'),      # ended, history still in RUN_1
        'case10': (5, 115, 'full'),       # running at outFreq 5
    }
    assert {n for n, p in got.items() if p.needs_you} == {
        'case5', 'case6', 'case7', 'case8', 'case9', 'case11'}
    assert [i.kind for i in got['case1'].items] == ['note']            # nothing to do
    assert [i.kind for i in got['case4'].items] == ['wait']
    assert got['case6'].post is None and needs(got['case6'])[0].startswith('last post job')
    assert 'archive/ pruned or missing' in needs(got['case8'])[0]
    assert needs(got['case11'])[0].startswith('holes on the cloud: no PLT for 450')
    assert got['case9'].state == 'skipped'
    assert [i.text for i in got['case5'].items if i.kind == 'history'] == [
        'organise history --update --clean --compile: RUN_1/riser.othd -> archive/riser2.othd']


def test_a_job_named_for_case1_does_not_make_case1_busy(dummy):
    got, _ = plans(dummy)
    assert got['case1'].state == 'done'
    assert got['case10'].state == 'running'
    assert any('named maincase1, not maincase10' in i.text for i in got['case10'].items)


def test_unreadable_queue_looks_at_no_case(dummy):
    subprocess.run([str(dummy / 'bin' / 'fake-slurm'), 'fail', 'on'], check=True,
                   env={**os.environ, 'FAKE_SLURM_DIR': str(dummy / 'slurm')})
    got, problems = plans(dummy)
    assert got == {} and 'the queue could not be read' in problems[0]


def test_show_changes_nothing(dummy):
    def tree():
        return sorted((str(p.relative_to(dummy)), p.stat().st_size, p.stat().st_mtime)
                      for p in dummy.rglob('*') if p.is_file())
    before = tree()
    plans(dummy)
    assert tree() == before


def test_a_completed_post_that_made_no_plt_needs_you(dummy):
    import json
    queue = json.loads((dummy / 'slurm' / 'queue.json').read_text())
    post4 = next(j for j in queue if j['name'] == 'postcase4')
    subprocess.run([str(dummy / 'bin' / 'fake-slurm'), 'finish', post4['jobid'], 'COMPLETED'],
                   check=True, env={**os.environ, 'FAKE_SLURM_DIR': str(dummy / 'slurm')})
    got, _ = plans(dummy)
    # it 'completed' after the .out of 650-800 were written but made no PLT
    # (it is fake): auto does not post them again blindly
    assert got['case4'].post is None
    assert needs(got['case4'])[0].startswith(f"post job {post4['jobid']} ended COMPLETED after "
                                             f"the .out of 650-800 (4) were written")


# --- which cases: the argument, `use case:`, or '*' -----------------------------

def test_no_case_is_an_error(dummy):
    with pytest.raises(AutoConfError, match='no case given'):
        resolve_cases(None, dummy / 'bare')


def test_one_case_from_anywhere_uses_its_folders_settings(dummy, tmp_path):
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    got, problems = plans(dummy, str(dummy / 'bare' / 'case3'), base=elsewhere)
    assert list(got) == ['case3'] and got['case3'].post == (550, 700, 'full')
    got, _ = plans(dummy, 'case3')                        # relative to the folder
    assert list(got) == ['case3']


def test_each_case_uses_its_own_folders_auto_conf(dummy, tmp_path):
    import json, shutil
    other = tmp_path / 'other'
    shutil.copytree(dummy / 'bare' / 'case5', other / 'case5')
    (other / '.auto.conf').write_text(f"remote = local\npath = {dummy / 'cloud' / 'bare'}\n")
    mixed = tmp_path / 'mixed'
    mixed.mkdir()
    (mixed / '.cases').write_text(json.dumps([
        {'name': 'case2', 'path': str(dummy / 'bare' / 'case2')},
        {'name': 'case5', 'path': str(other / 'case5')}]))
    results, confs, _ = gather(resolve_cases('*', mixed))
    assert set(confs) == {dummy / 'bare', other}
    assert {s.name for s, _ in results} == {'case2', 'case5'}
    assert confs[other].keep_rst is None and confs[dummy / 'bare'].keep_rst == 200


def test_a_folder_without_auto_conf_is_an_error(dummy, tmp_path):
    import shutil
    lone = tmp_path / 'lone'
    shutil.copytree(dummy / 'bare' / 'case2', lone / 'case2')
    with pytest.raises(AutoConfError, match='no .auto.conf'):
        gather(resolve_cases(str(lone / 'case2'), tmp_path))


def test_the_case_context(dummy, monkeypatch, capsys):
    import io
    from rich.console import Console
    from shellkit import Runtime
    from src.cli.app import create_app
    import shellkit.runtime
    monkeypatch.setenv('HOME', str(dummy / 'home'))
    monkeypatch.chdir(dummy / 'bare')
    # the runtime makes itself the current one; put the old one back after,
    # or its `use case:*` and folder leak into later tests
    monkeypatch.setattr(shellkit.runtime, '_current', shellkit.runtime._current)
    rt = Runtime(create_app(), console=Console(file=io.StringIO(), width=200, color_system=None),
                 err_console=Console(file=io.StringIO(), width=200, color_system=None))
    assert rt.execute_line('auto show') == 2                     # nothing set
    assert 'no case given' in capsys.readouterr().out
    assert rt.execute_line('use case:case3') == 0
    assert rt.execute_line('auto show') == 0
    out = capsys.readouterr().out
    assert 'case3  queued' in out and 'case2' not in out and 'summary' not in out
    assert rt.execute_line('use case:*') == 0
    assert rt.execute_line('auto show') == 1                     # some cases need you
    out = capsys.readouterr().out
    assert '11 cases' in out and 'summary' in out
