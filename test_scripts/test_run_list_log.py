"""`run list log`: a case's slurm-* files with the job type of each.

The type comes from the file: SLURM_JOB_NAME (pre<case>, main<case>,
post<case>, from `#SBATCH -J`) or else the banner the job script prints.
"""

import argparse
import io
import os

import pytest
from rich.console import Console

from shellkit import Runtime
from src.commands.run import RunCommand
from src.commands.run.list_impl import command as list_cmd


def _log(case, jobid, text, mtime, name=None):
    path = case / (name or f'slurm-{jobid}.out')
    path.write_text(text)
    os.utime(path, (mtime, mtime))
    return path


@pytest.fixture
def case(tmp_path):
    case = tmp_path / 'CaseX'
    case.mkdir()
    _log(case, 300, 'SLURM_JOB_ID = 300\nSLURM_JOB_NAME = preCaseX\n', 1000)
    _log(case, 100, 'SLURM_JOB_NAME = mainCaseX\n', 3000)
    _log(case, 200, '====\nFlexFlow Postprocessing Job\n====\n', 2000)    # older script
    _log(case, 400, 'hello\n', 4000)
    (case / 'postFlex.sh').write_text('')
    return case


@pytest.mark.parametrize('head, expected', [
    ('SLURM_JOB_NAME = preCH4SG3U1P1\n', ('pre', 'preCH4SG3U1P1')),
    ('SLURM_JOB_NAME = mainCase\nFlexFlow Postprocessing Job\n', ('main', 'mainCase')),
    ('FlexFlow Main Simulation Job\n', ('main', '')),
    ('FlexFlow Preprocessing Job\n', ('pre', '')),
    ('SLURM_JOB_NAME = myjob\n', ('other', 'myjob')),
    ('', ('other', '')),
])
def test_job_type(head, expected):
    assert list_cmd.job_type(head) == expected


def test_sort_by_time_type_and_jobid(case):
    logs = list_cmd.find_logs(case)
    ids = lambda key, reverse=False: [l['jobid'] for l in list_cmd.sort_logs(logs, key, reverse)]
    assert ids('time') == [300, 200, 100, 400]
    assert ids('time', reverse=True) == [400, 100, 200, 300]
    assert ids('type') == [300, 100, 200, 400]          # pre, main, post, other
    assert ids('jobid') == [100, 200, 300, 400]


def test_a_real_job_header_reads_as_pre(case):
    head = ("==========================================\n"
            "SLURM_CLUSTER_NAME = param-shakti\nSLURM_JOB_ID = 1200488\n"
            "SLURM_JOB_NAME = preCH4SG3U1P1\nSLURM_JOB_NODELIST = cn039\n")
    log = list_cmd.read_log(_log(case, 1200488, head, 5000))
    assert (log['jobid'], log['type'], log['name']) == (1200488, 'pre', 'preCH4SG3U1P1')


@pytest.fixture
def parse():
    parser = argparse.ArgumentParser()
    RunCommand().setup_parser(parser.add_subparsers(dest='command'))
    return lambda *words: parser.parse_args(['run', 'list', *words])


def test_parse(parse):
    args = parse('log', 'CaseX', '--sort', 'type', '-r', '--type', 'post', '--type', 'main')
    assert (args.what, args.case, args.sort, args.reverse, args.type) == \
        ('log', 'CaseX', 'type', True, ['post', 'main'])
    assert parse('log').sort == 'time'
    with pytest.raises(SystemExit):
        parse('log', '--sort', 'size')


@pytest.fixture
def rt(tmp_path, case, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    monkeypatch.chdir(tmp_path)
    from src.cli.app import create_app
    return Runtime(create_app(),
                   console=Console(file=io.StringIO(), width=200, color_system=None),
                   err_console=Console(file=io.StringIO(), width=200, color_system=None))


def _rows(text):
    return [line.split()[:2] for line in text.splitlines()
            if line.split() and line.split()[0].isdigit() and 'slurm-' in line]


def test_in_the_shell_with_the_case_context_and_a_pipe(rt, capsys):
    assert rt.execute_line('use case:CaseX') == 0
    assert rt.execute_line('run list log --type post --type other -r') == 0
    out = capsys.readouterr().out + rt.console.file.getvalue()
    assert _rows(out) == [['400', 'other'], ['200', 'post']]
    assert '2 file(s): 1 post, 1 other' in out

    piped = rt.run_captured('run list log --sort jobid')
    assert _rows(piped) == [['100', 'main'], ['200', 'post'], ['300', 'pre'], ['400', 'other']]
    assert 'file(s)' not in piped


def test_no_logs(tmp_path, capsys):
    list_cmd.execute_list(argparse.Namespace(what='log', case=str(tmp_path), type=None,
                                             sort='time', reverse=False, help=False))
    assert 'No slurm-* files' in capsys.readouterr().out
