"""tools/nas/simulation_functions.sh under BusyBox ash, the NAS's only shell.

A case with a restart, a redundant part, a gap, and missing/empty PLT files.
The clean functions must delete only after a yes, and need DELETE typed for
data no other part has.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / 'tools' / 'nas' / 'simulation_functions.sh'

pytestmark = pytest.mark.skipif(shutil.which('busybox') is None, reason='needs busybox')


def _part(path, steps):
    blocks = ''.join(f'tsId {t}\ntime 0\n1 2 3\n' for t in steps)
    path.write_text('mask 455\nnOths 1\n' + blocks)


@pytest.fixture
def case(tmp_path):
    case = tmp_path / 'C1'
    for d in ('binary', 'othd_files', 'oisd_files'):
        (case / d).mkdir(parents=True)
    (case / 'simflow.config').write_text('problem = riser\nouFreq = 1\noutFreq\t= 50  # every 50\n')
    othd = case / 'othd_files'
    _part(othd / 'riser1.othd', range(1, 101))
    _part(othd / 'riser2.othd', range(90, 151))     # restart
    _part(othd / 'riser3.othd', range(20, 41))      # inside riser1
    _part(othd / 'riser4.othd', range(160, 171))    # gap after 150
    _part(othd / 'riser5.othd', range(160, 171))    # duplicate of riser4
    _part(case / 'oisd_files' / 'riser1.oisd', range(1, 151))
    for t in range(50, 1001, 50):
        (case / 'binary' / f'riser.{t}.plt').write_text('x\n')
    (case / 'binary' / 'riser.300.plt').unlink()
    (case / 'binary' / 'riser.650.plt').unlink()
    (case / 'binary' / 'riser.700.plt').write_text('')
    return case


def ash(line, cwd, answer=''):
    return subprocess.run(['busybox', 'ash', '-c', f'. {SCRIPT}; {line}'], cwd=cwd,
                          input=answer, capture_output=True, text=True, timeout=60)


def test_show_plt_lists_only_missing_and_empty(case):
    r = ash('show_plt --case C1', case.parent)
    assert r.returncode == 1, r.stderr
    listed = [l for l in r.stdout.splitlines() if l.startswith(('missing', 'empty'))]
    assert listed == ['missing  C1/binary/riser.300.plt', 'missing  C1/binary/riser.650.plt',
                      'empty    C1/binary/riser.700.plt']
    assert 'steps 50..1000 every 50' in r.stdout          # outFreq and last PLT

    r = ash('show_plt --t2=200', case / 'binary')          # inside binary/, config one up
    assert r.returncode == 0 and 'All 4 PLT files are present' in r.stdout


@pytest.mark.parametrize('args, message', [
    ('--t1', '--t1 needs a value'),
    ('--freq 0', '--freq must be above 0'),
    ('--t1 x', 'needs a whole number'),
    ('--t1 500 --t2 100', 'is after'),
    ('--bogus', "unknown option '--bogus'"),
])
def test_show_plt_errors(case, args, message):
    r = ash(f'show_plt --case C1 {args}', case.parent)
    assert r.returncode == 2 and message in r.stderr


def test_show_archive_marks_restart_redundant_and_gap(case):
    r = ash('show_archive --case C1 --type othd', case.parent)
    assert r.returncode == 0, r.stderr
    notes = {l.split()[0]: l for l in r.stdout.splitlines() if l.strip().startswith('riser')}
    assert notes['riser1.othd'].rstrip().endswith('100')
    assert 'restart' in notes['riser2.othd']
    assert 'inside riser1.othd' in notes['riser3.othd']
    assert 'GAP' in notes['riser4.othd']
    assert 'inside riser4.othd' in notes['riser5.othd']
    assert '5 part(s), tsId 1..170, 2 redundant' in r.stdout


def _parts(case):
    return sorted(p.name for p in (case / 'othd_files').iterdir())


def test_clean_archive_deletes_a_redundant_part_after_yes(case):
    assert ash('clean_archive --case C1 --type othd --n 5:', case.parent, 'n\n').returncode == 0
    assert 'riser5.othd' in _parts(case)
    r = ash('clean_archive --case C1 --type othd --n 5:', case.parent, 'y\n')
    assert r.returncode == 0 and 'removed' in r.stdout
    assert _parts(case) == ['riser1.othd', 'riser2.othd', 'riser3.othd', 'riser4.othd']


def test_clean_archive_needs_delete_typed_for_data_loss(case):
    r = ash('clean_archive --case C1 --type othd --n 2:3', case.parent, 'y\n')
    assert 'riser2.othd is not redundant' in r.stdout and 'Cancelled' in r.stdout
    assert len(_parts(case)) == 5
    r = ash('clean_archive --case C1 --type oisd --n 1', case.parent, 'y\n')
    assert 'ALL the oisd parts' in r.stdout
    assert (case / 'oisd_files' / 'riser1.oisd').exists()
    ash('clean_archive --case C1 --type othd --n 2', case.parent, 'DELETE\n')
    assert 'riser2.othd' not in _parts(case)


def test_clean_archive_needs_a_range_and_honours_dry_run(case):
    r = ash('clean_archive --case C1', case.parent)
    assert r.returncode == 2 and 'which parts?' in r.stderr
    r = ash('clean_archive --case C1 --n 3 --dry-run', case.parent)
    assert 'Dry run' in r.stdout and len(_parts(case)) == 5
    r = ash('clean_archive_files --n1 5 --case C1 --type othd', case.parent, 'y\n')   # old name
    assert 'riser5.othd' not in _parts(case)


def test_clean_plt_window_and_freq(case):
    r = ash('clean_plt --case C1 --t1 100 --t2 900 --dry-run', case.parent)
    assert '15 file(s)' in r.stdout and 'Dry run' in r.stdout
    r = ash('clean_plt --case C1 --t1 100 --t2 900 --freq 200', case.parent, 'y\n')
    assert r.returncode == 0 and 'Removed 4 file(s)' in r.stdout
    left = {int(p.name.split('.')[1]) for p in (case / 'binary').iterdir()}
    assert left.isdisjoint({100, 500, 700, 900}) and {50, 200, 1000} <= left
    r = ash('clean_plt --case C1 --t1 10', case.parent)
    assert r.returncode == 2 and 'needs --t1 and --t2' in r.stderr
