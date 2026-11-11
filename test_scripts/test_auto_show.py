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
    results, confs, problems = gather(resolve_cases(case, base or dummy / 'bare'), 'local')
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
        'case11': (650, 700, 'full'),     # 450 lost; 650-700 still posted
        'case12': (565, 600, 'full'),     # wrote every 50, then every 5: only 565-600 left
    }
    assert {n for n, p in got.items() if p.needs_you} == {
        'case5', 'case6', 'case7', 'case8', 'case9', 'case11', 'case12'}
    assert {i.kind for i in got['case1'].items} == {'note'}            # nothing to do
    assert [i.text for i in got['case1'].items] == [
        'The newest run is archive/riser1.othd (steps 1–1000). Its output steps: '
        '50–1000 every 50 (20 steps).',
        'No post job needed: all 20 output steps have a PLT (20 on local). Matched by file name '
        'and size; the md5 is checked before anything is deleted.']
    assert [i.kind for i in got['case4'].items] == ['wait']
    assert got['case6'].post is None and needs(got['case6'])[0].startswith('Post job')
    assert 'archive/ is pruned or missing' in needs(got['case8'])[0]
    assert needs(got['case11'])[0].startswith('Step 450 has no PLT and no .out anywhere')
    assert got['case9'].state == 'skipped'
    assert [i.text for i in got['case5'].items if i.kind == 'history'] == [
        'Move RUN_1/riser.othd and .oisd into archive/ as run 2, then clean and compile '
        '(organise history --update --clean --compile)']


def test_a_job_named_for_case1_does_not_make_case1_busy(dummy):
    got, _ = plans(dummy)
    assert got['case1'].state == 'done'
    assert got['case10'].state == 'running'
    assert any('named maincase1; for this case it should be maincase10' in i.text for i in got['case10'].items)


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
    assert needs(got['case4'])[0].startswith(f"Post job {post4['jobid']} ended COMPLETED after "
                                             f"the .out of steps 650–800 every 50 (4 steps) were written")


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
    import shutil
    from src.core import cases_file
    other = tmp_path / 'other'
    shutil.copytree(dummy / 'bare' / 'case5', other / 'case5')
    cases_file.write(cases_file.CasesFile(cases_file.path_for(other),
                                          remotes={'local': str(dummy / 'cloud' / 'bare')}))
    mixed = tmp_path / 'mixed'
    mixed.mkdir()
    cases_file.write(cases_file.CasesFile(cases_file.path_for(mixed), cases=[
        {'name': 'case2', 'path': str(dummy / 'bare' / 'case2')},
        {'name': 'case5', 'path': str(other / 'case5')}]))
    results, confs, _ = gather(resolve_cases('*', mixed), 'local')
    assert set(confs) == {dummy / 'bare', other}
    assert {s.name for s, _ in results} == {'case2', 'case5'}
    assert confs[other].keep_rst is None and confs[dummy / 'bare'].keep_rst == 200


def test_a_folder_without_auto_conf_is_an_error(dummy, tmp_path):
    import shutil
    lone = tmp_path / 'lone'
    shutil.copytree(dummy / 'bare' / 'case2', lone / 'case2')
    with pytest.raises(AutoConfError, match='no .cases.yml'):
        gather(resolve_cases(str(lone / 'case2'), tmp_path), 'local')


def test_the_remote_must_be_named_and_listed(dummy):
    case = resolve_cases('case2', dummy / 'bare')
    with pytest.raises(AutoConfError, match='which remote'):
        gather(case, None)
    with pytest.raises(AutoConfError, match="no folder for remote 'cloud'"):
        gather(case, 'cloud')


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
    assert rt.execute_line('auto show --remote local') == 2      # no case set
    assert 'no case given' in capsys.readouterr().out
    assert rt.execute_line('use case:case3') == 0
    assert rt.execute_line('auto show') == 2                     # no remote set
    assert 'which remote' in capsys.readouterr().out
    assert rt.execute_line('auto show --remote local') == 0
    out = capsys.readouterr().out
    assert 'case3  queued' in out and 'case2' not in out and 'summary' not in out
    # a case reads as labelled sections
    for heading in ('State', 'History', 'PLT files', 'OUT files', 'RST files',
                    'Inputs and case files', 'Steps:', 'Remote:', 'Action:'):
        assert heading in out
    assert 'main 1300105 PENDING, restarts from 700' in out
    assert '1: run post full case3 --t1 550 --t2 700 --no-remote' in out
    assert rt.execute_line('use case:*') == 0
    assert rt.execute_line('auto show --remote local') == 1      # some cases need you
    out = capsys.readouterr().out
    assert '12 cases' in out and 'summary' in out
    assert 'PLT files' not in out                                # table only for several
    assert rt.execute_line('auto show --remote local --detail --only plt') == 1
    out = capsys.readouterr().out
    assert out.count('PLT files') == 11 and 'RST files' not in out   # case9 has none
    assert rt.execute_line('auto show --remote local --only nonsense') == 2


# --- the report, auto commands, auto status --------------------------------------------

def report_of(dummy, case):
    from src.core.auto.report import build
    results, confs, _ = gather(resolve_cases(case, dummy / 'bare'), 'local')
    snap, plan = results[0]
    return {sec.key: sec for sec in build(snap, plan, confs[snap.dir.parent])}


def test_report_sections_of_a_queued_case(dummy):
    sec = report_of(dummy, 'case3')
    assert list(sec) == ['state', 'history', 'plt', 'out', 'rst', 'inputs']
    state = dict(sec['state'].rows)
    assert state['Steps'] == '760 of 1000 (76%)'
    assert state['Job'] == 'main 1300105 PENDING, restarts from 700'
    assert state['Last jobs'].startswith('main 1300104 TIMEOUT, ended ')
    plt = dict(sec['plt'].rows)
    assert sec['plt'].subtitle == 'run RUN_1/riser.othd: output steps 550–700 every 50 (4 steps)'
    # everything the remote holds, then what the run needs that is not there
    assert plt['Remote'] == ('present 50–500 every 50 (10 steps) · missing 550–700 every 50 '
                             '(4 steps)')
    assert plt['Binary'] == 'present 750 · broken none'
    assert plt['Skipped'] == '750: the queued job restarts from 700 and computes it again'
    assert sec['plt'].actions == ['run post full case3 --t1 550 --t2 700 --no-remote']
    assert sec['rst'].actions[0] == 'case upload rst case3 --t1 700 --t2 700 --to local'
    assert sec['rst'].actions[1].startswith('auto apply: delete .rst of steps 550, 650')
    assert dict(sec['history'].rows)['Run dir'].startswith('riser.othd steps 501–760')


def test_report_needs_and_flags_come_after_state(dummy):
    sec = report_of(dummy, 'case6')
    assert list(sec)[:3] == ['state', 'needs', 'flags']
    assert dict(sec['plt'].rows)['Binary'] == 'present 450, 500 · broken 550'
    assert sec['plt'].actions[0] == 'case upload binary case6 --t1 450 --t2 500 --missing --to local'


def test_auto_commands_is_plain_text_to_read_or_save(dummy, monkeypatch, capsys):
    from types import SimpleNamespace
    from src.commands.auto.show import execute_commands
    monkeypatch.chdir(dummy / 'bare')
    assert execute_commands(SimpleNamespace(case='*', remote='local')) == 0
    out = capsys.readouterr().out
    assert '\x1b[' not in out                                     # no colour codes
    assert 'run post full case2 --t1 450 --t2 600 --no-remote    # 1, PLT files' in out
    assert '#   wait: post job' in out                            # case4
    assert '#   needs you: Main job' in out                       # case7
    assert '#   auto apply: delete' in out


def test_auto_status_one_line_per_case(dummy, monkeypatch, capsys):
    from types import SimpleNamespace
    from src.commands.auto.show import execute_status
    monkeypatch.chdir(dummy / 'bare')
    assert execute_status(SimpleNamespace(case='*', remote='local')) == 1   # some need you
    out = ' '.join(capsys.readouterr().out.split())
    assert 'case4 post running 800/1000 post running waits for post job' in out
    assert 'case1 done 1000/1000 - nothing' in out


def test_a_change_of_output_frequency_is_not_a_hole(dummy):
    """case12 wrote every 50 steps up to 500 and every 5 after (outFreq says 5 now)."""
    sec = report_of(dummy, 'case12')
    plt = dict(sec['plt'].rows)
    assert sec['plt'].subtitle == ('run archive/riser1.othd: output steps 50–500 every 50 '
                                   '(10 steps), 505–600 every 5 (20 steps)')
    assert plt['Remote'] == ('present 50–500 every 50 (10 steps), 505–560 every 5 (12 steps) · '
                             'missing 565–600 every 5 (8 steps)')
    assert 'Lost' not in plt
    assert sec['plt'].actions == ['run post full case12 --t1 565 --t2 600 --no-remote']
