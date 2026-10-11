"""Tests for `case organise archive --update/--clean/--compile`.

--compile merges the archived parts into compiled/{problem}.othd|oisd. A
restart reruns timesteps already written, so a tsId at or below one already
taken drops everything from there on in favour of the restarted run -- the
same "later run wins" rule the readers apply. --clean asks about every
redundant file in turn; a file the user keeps must survive and be renumbered.
"""

from argparse import Namespace
from types import SimpleNamespace

from rich.console import Console

from src.commands.case.organise_impl.organizer import CaseOrganizer
from src.core.readers.othd_reader import OTHDReader

HEADER = "mask 455\nnOths 1\n"


def othd(ts_ids, value=0.0, header=HEADER):
    """A one-node OTHD whose displacement records which file a step came from."""
    blocks = "".join(f"tsId {t}\ntime {t * 0.05}\nothId 0\naleDisp 3 1\n"
                     f"{value} {t} 0.0\n" for t in ts_ids)
    return header + blocks


class _Logger:
    def __getattr__(self, name):
        return lambda *a, **k: None


def make_organizer(case_dir, **flags):
    args = Namespace(update=False, clean=False, compile=False, dry_run=False,
                     no_confirm=False, log=False, verbose=False, t1=None, t2=None)
    for key, value in flags.items():
        setattr(args, key, value)
    case = SimpleNamespace(case_directory=str(case_dir), problem_name='riser',
                           config={'dir': './RUN_1'})
    return CaseOrganizer(case, args, _Logger(), Console(file=open('/dev/null', 'w')))


def write_parts(case_dir, parts):
    othd_dir = case_dir / 'othd_files'
    othd_dir.mkdir(exist_ok=True)
    for name, text in parts.items():
        (othd_dir / name).write_text(text)
    return othd_dir


def test_compile_restart_replaces_the_tail_of_the_earlier_run(tmp_path):
    othd_dir = write_parts(tmp_path, {
        'riser1.othd': othd(range(1, 8), value=1.0),
        'riser2.othd': othd(range(5, 11), value=2.0),   # restart from 4
    })
    make_organizer(tmp_path, compile=True).organize('archive')

    compiled = othd_dir / 'compiled' / 'riser.othd'
    assert compiled.read_text().count('mask 455') == 1
    reader = OTHDReader(str(compiled))
    assert reader.tsIds == list(range(1, 11))
    sources = [reader.displacements[(0, i, 0)][0] for i in range(10)]
    assert sources == [1.0] * 4 + [2.0] * 6
    # the parts are kept
    assert sorted(p.name for p in othd_dir.glob('*.othd')) == ['riser1.othd', 'riser2.othd']


def test_compile_restart_inside_one_file(tmp_path):
    othd_dir = write_parts(tmp_path, {'riser1.othd': othd([1, 2, 3, 4, 3, 4, 5])})
    make_organizer(tmp_path, compile=True).organize('archive')
    reader = OTHDReader(str(othd_dir / 'compiled' / 'riser.othd'))
    assert reader.tsIds == [1, 2, 3, 4, 5]


def test_compile_refuses_parts_with_different_headers(tmp_path):
    othd_dir = write_parts(tmp_path, {
        'riser1.othd': othd([1, 2]),
        'riser2.othd': othd([3, 4], header="mask 455\nnOths 2\n"),
    })
    make_organizer(tmp_path, compile=True).organize('archive')
    assert not (othd_dir / 'compiled').exists()


def test_compile_dry_run_writes_nothing(tmp_path):
    othd_dir = write_parts(tmp_path, {'riser1.othd': othd([1, 2])})
    make_organizer(tmp_path, compile=True, dry_run=True).organize('archive')
    assert not (othd_dir / 'compiled').exists()


def test_archive_without_flags_does_nothing(tmp_path):
    run_dir = tmp_path / 'RUN_1'
    run_dir.mkdir()
    (run_dir / 'riser.othd').write_text(othd([1, 2]))
    make_organizer(tmp_path).organize('archive')
    assert (run_dir / 'riser.othd').exists()
    assert not (tmp_path / 'othd_files').exists()


def test_update_moves_with_next_number(tmp_path):
    write_parts(tmp_path, {'riser1.othd': othd([1, 2])})
    run_dir = tmp_path / 'RUN_1'
    run_dir.mkdir()
    (run_dir / 'riser.othd').write_text(othd([3, 4]))
    make_organizer(tmp_path, update=True).organize('archive')
    assert not (run_dir / 'riser.othd').exists()
    assert (tmp_path / 'othd_files' / 'riser2.othd').exists()


def _answers(monkeypatch, *answers):
    it = iter(answers)
    monkeypatch.setattr('builtins.input', lambda *a: next(it))


def test_clean_keeps_a_file_the_user_declines(tmp_path, monkeypatch):
    othd_dir = write_parts(tmp_path, {
        'riser1.othd': othd(range(1, 11)),
        'riser2.othd': othd(range(3, 6)),     # subset of riser1
        'riser3.othd': othd(range(11, 15)),
        'riser4.othd': othd(range(12, 14)),   # subset of riser3
    })
    _answers(monkeypatch, 'n', 'y', 'y')      # keep riser2, delete riser4, apply renames
    make_organizer(tmp_path, clean=True).organize('archive')

    names = sorted(p.name for p in othd_dir.glob('*.othd'))
    assert names == ['riser1.othd', 'riser2.othd', 'riser3.othd']
    assert OTHDReader(str(othd_dir / 'riser2.othd')).tsIds == [3, 4, 5]


def test_clean_quit_changes_nothing(tmp_path, monkeypatch):
    othd_dir = write_parts(tmp_path, {
        'riser1.othd': othd(range(1, 11)),
        'riser5.othd': othd(range(3, 6)),
    })
    before = sorted(p.name for p in othd_dir.glob('*.othd'))
    _answers(monkeypatch, 'q')
    make_organizer(tmp_path, clean=True).organize('archive')
    assert sorted(p.name for p in othd_dir.glob('*.othd')) == before


def test_clean_declined_renames_leave_names(tmp_path, monkeypatch):
    othd_dir = write_parts(tmp_path, {
        'riser1.othd': othd(range(1, 11)),
        'riser2.othd': othd(range(3, 6)),
        'riser3.othd': othd(range(11, 15)),
    })
    _answers(monkeypatch, 'y', 'n')           # delete riser2, decline renaming riser3 → riser2
    make_organizer(tmp_path, clean=True).organize('archive')
    assert sorted(p.name for p in othd_dir.glob('*.othd')) == ['riser1.othd', 'riser3.othd']
