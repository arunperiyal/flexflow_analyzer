"""`case status`: the case's notes in .casestatus.md, shown under what its
files say now. `case status update` edits them, adds a log line or sets the
state; the job scripts add their own log lines in the same format."""

import argparse
import io
import re
import subprocess
from pathlib import Path

import pytest
from rich.console import Console

from src.core import case_status as cs
from src.commands.case.status_impl import command as status

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / 'src' / 'templates' / 'scripts'


@pytest.fixture
def case(tmp_path):
    case = tmp_path / 'C1'
    (case / 'binary').mkdir(parents=True)
    (case / 'simflow.config').write_text('problem = riser\nnp = 8\noutFreq = 50\n'
                                         'restartFlag = 1\nrestartTsId = 400\n')
    (case / 'riser.def').write_text('timeSteppingControl{\n maxTimeSteps = 1000\n}\n')
    (case / 'binary' / 'riser.450.plt').write_text('x')
    (case / 'othd_files').mkdir()
    (case / 'othd_files' / 'riser1.othd').write_text(
        'mask 1\n' + ''.join(f'tsId {t}\n1\n' for t in range(1, 501)))
    return case


def run(case_dir, monkeypatch, **kw):
    monkeypatch.setattr(status, 'Console',
                        lambda: Console(file=buf, width=120, color_system=None))
    buf = io.StringIO()
    monkeypatch.setattr(status, '_queued_jobs', lambda name: [])
    ns = dict(what=None, case=str(case_dir), message=None, state=None, no_create=False, help=False)
    ns.update(kw)
    code = status.execute_status(argparse.Namespace(**ns))
    return code, buf.getvalue()


# --- the file ----------------------------------------------------------------

def test_template_and_header(case):
    assert cs.ensure(case) and not cs.ensure(case)
    meta, body = cs.read(case)
    assert meta == {'state': 'new', 'tags': []}
    assert body.startswith('# C1\n') and re.search(r'## Log\n- \d{4}-\d\d-\d\d \d\d:\d\d  created\n$', body)


def test_log_lines_go_at_the_end_of_the_log_section(case):
    cs.path_for(case).write_text('---\nstate: new\ntags: [a, b]\n---\n# C1\n\n## Log\n'
                                 '- old\n\n\n## Later\ntext\n')
    cs.add_log(case, 'first\nsecond line', when=0)
    text = cs.path_for(case).read_text()
    assert '## Log\n- old\n- 1970-01-01' in text.replace(cs.stamp(0), '1970-01-01')
    assert text.endswith('  first\n-     second line\n\n## Later\ntext\n')
    assert cs.read(case)[0]['tags'] == ['a', 'b']
    assert cs.with_log_line('# X\n', 'y') == '# X\n\n## Log\n- y\n'


def test_set_state_logs_the_change(case):
    cs.ensure(case)
    assert cs.set_state(case, 'running') == 'new'
    assert cs.set_state(case, 'running') == 'running'          # no second log line
    meta, body = cs.read(case)
    assert meta['state'] == 'running'
    assert body.count('state: new -> running') == 1
    assert cs.last_log_line(body).endswith('state: new -> running')
    with pytest.raises(ValueError):
        cs.set_state(case, 'sleeping')


# --- the command ---------------------------------------------------------------

def test_show_writes_the_file_the_first_time(case, monkeypatch):
    code, text = run(case, monkeypatch)
    assert code == 0 and cs.path_for(case).exists()
    assert 'wrote .casestatus.md' in text
    assert 'problem riser · np 8 · outFreq 50 · maxTimeSteps 1000' in text
    assert 'step 500 of 1000 (50%)' in text and 'from 400' in text
    assert 'binary/ up to 450' in text
    _, again = run(case, monkeypatch)
    assert 'wrote' not in again


def test_show_lists_the_recorded_restarts(case, monkeypatch):
    from src.core import restarts
    restarts.write(case, [dict(after=str(a), first=str(a + 1), time='-', reached='-', replaced='0',
                               part='-', previous='-', recorded='-') for a in (100, 200)])
    _, text = run(case, monkeypatch)
    assert 'after 100, 200  (2 in .restarts)' in text


def test_show_no_create(case, monkeypatch):
    code, text = run(case, monkeypatch, no_create=True)
    assert code == 0 and not cs.path_for(case).exists() and 'no .casestatus.md here' in text


def test_update_message_and_state(case, monkeypatch):
    assert run(case, monkeypatch, what='update', message='lock-in from U=5.5')[0] == 0
    code, text = run(case, monkeypatch, what='update', state='done')
    assert code == 0 and 'new → done' in text
    meta, body = cs.read(case)
    assert meta['state'] == 'done' and 'lock-in from U=5.5' in body
    _, shown = run(case, monkeypatch)
    assert 'done' in shown.splitlines()[1] and 'lock-in from U=5.5' in shown


def test_update_opens_the_editor(case, monkeypatch):
    calls = []
    monkeypatch.setenv('EDITOR', 'myedit --wait')
    monkeypatch.setattr(status.subprocess, 'call', lambda cmd: calls.append(cmd) or 0)
    assert run(case, monkeypatch, what='update')[0] == 0
    assert calls == [['myedit', '--wait', str(cs.path_for(case))]]


def test_without_editor_set_vi_comes_first(case, monkeypatch):
    calls = []
    monkeypatch.delenv('VISUAL', raising=False)
    monkeypatch.delenv('EDITOR', raising=False)
    monkeypatch.setattr(status.shutil, 'which', lambda e: f'/usr/bin/{e}' if e != 'vi' else None)
    monkeypatch.setattr(status.subprocess, 'call', lambda cmd: calls.append(cmd) or 0)
    run(case, monkeypatch, what='update')
    assert calls[0][0] == 'vim'                       # no vi: vim, before nano
    monkeypatch.setattr(status.shutil, 'which', lambda e: f'/usr/bin/{e}')
    run(case, monkeypatch, what='update')
    assert calls[1][0] == 'vi'


def test_missing_case_and_wildcard_update(case, monkeypatch, tmp_path):
    assert run(case, monkeypatch, case=str(tmp_path / 'nope'))[0] == 1
    assert run(case, monkeypatch, what='update', case='*')[0] == 2


def test_the_first_word_is_the_case_unless_it_is_update(case, monkeypatch):
    code, text = run(case, monkeypatch, what=str(case), case=None)
    assert code == 0 and 'step 500' in text


def test_report_state_column(case):
    from src.commands.case.report_impl.command import _state
    assert 'dim' in _state(case)
    cs.ensure(case)
    cs.set_state(case, 'failed')
    assert _state(case) == '[bold red]failed[/]'


# --- the job scripts -----------------------------------------------------------

def _helpers(script):
    text = (SCRIPTS / script).read_text()
    start = text.index('CASESTATUS=')
    last = max(text.find('casestatus_log() {'), text.find('casestatus_state() {'))
    end = text.index('\n}\n', last) + 3
    return text[start:end]


@pytest.mark.parametrize('script', ['mainFlex.sh', 'postFlex.sh'])
def test_script_helpers_write_the_same_format(case, script):
    cs.ensure(case)
    cs.add_log(case, 'from python')
    (case / '## Later').write_text('')            # a heading-looking file name is harmless
    calls = 'casestatus_log "job line one"; casestatus_log "job line two"'
    if script == 'mainFlex.sh':
        calls += '; casestatus_state running'
    r = subprocess.run(['bash', '-c', _helpers(script) + '\n' + calls], cwd=case,
                       env={'SLURM_SUBMIT_DIR': str(case), 'SLURM_JOB_ID': '42', 'PATH': '/usr/bin:/bin'},
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    meta, body = cs.read(case)
    log = [l.split('  ', 1)[1] for l in body.splitlines() if l.startswith('- ')]
    want = ['created', 'from python', 'job line one', 'job line two']
    if script == 'mainFlex.sh':
        want.append('state: new -> running')
        assert meta['state'] == 'running'
    assert log == want
    # and python appends after the job's lines
    cs.add_log(case, 'python again')
    assert cs.last_log_line(cs.read(case)[1]).endswith('python again')


def test_script_helper_makes_the_file(tmp_path):
    case = tmp_path / 'C9'
    case.mkdir()
    r = subprocess.run(['bash', '-c', _helpers('mainFlex.sh') + '\ncasestatus_state running'],
                       env={'SLURM_SUBMIT_DIR': str(case), 'SLURM_JOB_ID': '7', 'PATH': '/usr/bin:/bin'},
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    meta, body = cs.read(case)
    assert meta['state'] == 'running' and body.startswith('# C9')
    assert [l.split('  ', 1)[1] for l in body.splitlines() if l.startswith('- ')] == [
        'notes started by job 7', 'state: new -> running']


@pytest.mark.parametrize('script', ['mainFlex.sh', 'postFlex.sh'])
def test_scripts_still_parse(script):
    assert subprocess.run(['bash', '-n', str(SCRIPTS / script)]).returncode == 0
