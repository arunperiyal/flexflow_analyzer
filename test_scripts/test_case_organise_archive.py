"""Tests for `case organise archive --update/--clean/--compile`.

--compile merges the archived parts into compiled/{problem}.othd|oisd. A
restart reruns timesteps already written, so a tsId at or below one already
taken drops everything from there on in favour of the restarted run -- the
same "later run wins" rule the readers apply. --clean asks about every
redundant file in turn; a file the user keeps must survive and be renumbered.
"""

from argparse import Namespace

import pytest
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
    args = Namespace(update=False, verify=False, clean=False, compile=False, prune=False,
                     dry_run=False,
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


def test_verify_flags_a_cut_off_last_step_and_stops_compile(tmp_path):
    text = othd([1, 2, 3])
    othd_dir = write_parts(tmp_path, {
        'riser1.othd': text,
        'riser2.othd': text[:-12],            # killed mid-write
    })
    organizer = make_organizer(tmp_path, verify=True, compile=True)
    organizer.organize('archive')
    assert organizer.stats['verify_ok'] is False
    assert not (othd_dir / 'compiled').exists()

    _, _, problems, _ = organizer._check_file(othd_dir / 'riser2.othd')
    assert any('incomplete last step (tsId 3)' in p for p in problems)


def test_verify_accepts_good_files_and_restarts(tmp_path):
    othd_dir = write_parts(tmp_path, {'riser1.othd': othd([1, 2, 3, 2, 3, 4])})
    organizer = make_organizer(tmp_path, verify=True)
    organizer.organize('archive')
    assert organizer.stats['verify_ok'] is True
    assert organizer._check_file(othd_dir / 'riser1.othd') == (6, (1, 4), [], 1)


def test_prune_puts_the_compiled_file_in_place_of_the_parts(tmp_path):
    othd_dir = write_parts(tmp_path, {
        'riser1.othd': othd(range(1, 8), value=1.0),
        'riser2.othd': othd(range(5, 11), value=2.0),
    })
    make_organizer(tmp_path, compile=True).organize('archive')
    compiled = (othd_dir / 'compiled' / 'riser.othd').read_bytes()

    make_organizer(tmp_path, prune=True, no_confirm=True).organize('archive')
    assert sorted(p.name for p in othd_dir.iterdir()) == ['riser1.othd']
    assert (othd_dir / 'riser1.othd').read_bytes() == compiled


def test_prune_then_update_keeps_the_history(tmp_path):
    othd_dir = write_parts(tmp_path, {
        'riser1.othd': othd(range(1, 8), value=1.0),
        'riser2.othd': othd(range(5, 11), value=2.0),
    })
    make_organizer(tmp_path, compile=True, prune=True, no_confirm=True).organize('archive')

    run_dir = tmp_path / 'RUN_1'
    run_dir.mkdir()
    (run_dir / 'riser.othd').write_text(othd(range(9, 13), value=3.0))   # restart from 8
    make_organizer(tmp_path, update=True, compile=True).organize('archive')
    assert sorted(p.name for p in othd_dir.glob('*.othd')) == ['riser1.othd', 'riser2.othd']

    reader = OTHDReader(str(othd_dir / 'compiled' / 'riser.othd'))
    assert reader.tsIds == list(range(1, 13))
    sources = [reader.displacements[(0, i, 0)][0] for i in range(12)]
    assert sources == [1.0] * 4 + [2.0] * 4 + [3.0] * 4


def test_prune_finishes_a_compiled_file_left_without_parts(tmp_path):
    # The state the first --prune left behind: compiled/ and nothing else.
    othd_dir = tmp_path / 'othd_files'
    (othd_dir / 'compiled').mkdir(parents=True)
    (othd_dir / 'compiled' / 'riser.othd').write_text(othd([1, 2, 3]))
    make_organizer(tmp_path, prune=True, dry_run=True).organize('archive')
    assert (othd_dir / 'compiled' / 'riser.othd').exists()

    make_organizer(tmp_path, prune=True).organize('archive')   # moves without asking
    assert sorted(p.name for p in othd_dir.iterdir()) == ['riser1.othd']
    assert OTHDReader(str(othd_dir / 'riser1.othd')).tsIds == [1, 2, 3]


def test_prune_dry_run_changes_nothing(tmp_path):
    othd_dir = write_parts(tmp_path, {'riser1.othd': othd([1, 2]), 'riser2.othd': othd([3, 4])})
    make_organizer(tmp_path, compile=True).organize('archive')
    before = sorted(str(p.relative_to(othd_dir)) for p in othd_dir.rglob('*'))
    make_organizer(tmp_path, prune=True, dry_run=True).organize('archive')
    assert sorted(str(p.relative_to(othd_dir)) for p in othd_dir.rglob('*')) == before


def test_prune_refuses_an_out_of_date_compiled_file(tmp_path):
    othd_dir = write_parts(tmp_path, {'riser1.othd': othd([1, 2])})
    make_organizer(tmp_path, compile=True).organize('archive')
    (othd_dir / 'riser2.othd').write_text(othd([3, 4]))
    make_organizer(tmp_path, prune=True, no_confirm=True).organize('archive')
    assert sorted(p.name for p in othd_dir.glob('*.othd')) == ['riser1.othd', 'riser2.othd']


def test_prune_asks_first(tmp_path, monkeypatch):
    othd_dir = write_parts(tmp_path, {'riser1.othd': othd([1, 2])})
    make_organizer(tmp_path, compile=True).organize('archive')
    _answers(monkeypatch, 'n')
    make_organizer(tmp_path, prune=True).organize('archive')
    assert (othd_dir / 'riser1.othd').exists()


# A run that stopped before its first step leaves a part with only the header
# (or nothing at all). --clean used to abort on it ("No time steps found");
# it holds no data, so it is offered for deletion like a redundant part.

def test_clean_offers_a_part_with_no_time_steps(tmp_path, monkeypatch):
    othd_dir = write_parts(tmp_path, {
        'riser1.othd': othd(range(1, 11)),
        'riser2.othd': HEADER,                # header only
        'riser3.othd': '',                    # empty file
        'riser4.othd': othd(range(11, 21)),
    })
    _answers(monkeypatch, 'y', 'y', 'y')      # delete riser2, riser3, apply renames
    make_organizer(tmp_path, clean=True).organize('archive')
    assert sorted(p.name for p in othd_dir.glob('*.othd')) == ['riser1.othd', 'riser2.othd']
    assert OTHDReader(str(othd_dir / 'riser2.othd')).tsIds == list(range(11, 21))


def test_clean_keeps_an_empty_part_without_overwriting_it(tmp_path, monkeypatch):
    othd_dir = write_parts(tmp_path, {
        'riser1.othd': othd(range(1, 11)),
        'riser2.othd': HEADER,
        'riser3.othd': othd(range(11, 21)),
    })
    _answers(monkeypatch, 'n', 'y')           # keep the empty part, apply renames
    make_organizer(tmp_path, clean=True).organize('archive')
    assert sorted(p.name for p in othd_dir.glob('*.othd')) == \
        ['riser1.othd', 'riser2.othd', 'riser3.othd']
    assert OTHDReader(str(othd_dir / 'riser2.othd')).tsIds == list(range(11, 21))
    assert (othd_dir / 'riser3.othd').read_text() == HEADER


def test_clean_still_aborts_on_a_part_it_cannot_read(tmp_path, monkeypatch):
    othd_dir = write_parts(tmp_path, {
        'riser1.othd': othd(range(1, 11)),
        'riser2.othd': HEADER + "tsIdx garbage\n",   # mentions tsId, yields no step
    })
    _answers(monkeypatch)
    import pytest
    with pytest.raises(SystemExit):
        make_organizer(tmp_path, clean=True).organize('archive')
    assert sorted(p.name for p in othd_dir.glob('*.othd')) == ['riser1.othd', 'riser2.othd']


# --- .restarts: where the runs took over, kept past --compile and --prune -----

from src.core import restarts as rs


def _rows(case_dir):
    return [(int(r['after']), int(r['first']), r['time'], int(r['reached']), int(r['replaced']),
             r['part'], r['previous']) for r in rs.read(case_dir)]


def test_compile_records_the_restarts(tmp_path):
    write_parts(tmp_path, {
        'riser1.othd': othd(range(1, 8)),
        'riser2.othd': othd(range(5, 11)),     # resumed after 4: 5..7 computed again
        'riser3.othd': othd(range(11, 15)),    # resumed after 10, no overlap
    })
    make_organizer(tmp_path, compile=True).organize('archive')
    assert _rows(tmp_path) == [
        (4, 5, f"{5 * 0.05:.6e}", 7, 3, 'riser2.othd', 'riser1.othd'),
        (10, 11, f"{11 * 0.05:.6e}", 10, 0, 'riser3.othd', 'riser2.othd')]
    text = rs.path_for(tmp_path).read_text()
    assert text.startswith('# Restarts of ') and '# after' in text


def test_restart_inside_one_file_is_recorded(tmp_path):
    write_parts(tmp_path, {'riser1.othd': othd([1, 2, 3, 4, 3, 4, 5])})
    make_organizer(tmp_path, compile=True).organize('archive')
    assert _rows(tmp_path) == [(2, 3, f"{3 * 0.05:.6e}", 4, 2, 'riser1.othd', 'riser1.othd')]


def test_restarts_survive_prune_and_grow(tmp_path):
    othd_dir = write_parts(tmp_path, {
        'riser1.othd': othd(range(1, 8), value=1.0),
        'riser2.othd': othd(range(5, 11), value=2.0),
    })
    make_organizer(tmp_path, compile=True, prune=True, no_confirm=True).organize('archive')
    assert [r[0] for r in _rows(tmp_path)] == [4]
    first = rs.path_for(tmp_path).read_text()

    # the parts are gone; compiling again must not forget the restart after 4
    make_organizer(tmp_path, compile=True).organize('archive')
    assert rs.path_for(tmp_path).read_text() == first

    run_dir = tmp_path / 'RUN_1'
    run_dir.mkdir()
    (run_dir / 'riser.othd').write_text(othd(range(9, 13), value=3.0))   # after 8
    make_organizer(tmp_path, update=True, compile=True).organize('archive')
    assert [(r[0], r[4], r[5]) for r in _rows(tmp_path)] == [(4, 3, 'riser2.othd'),
                                                              (8, 2, 'riser2.othd')]


def test_no_restart_no_file_and_dry_run_writes_none(tmp_path):
    write_parts(tmp_path, {'riser1.othd': othd(range(1, 8))})
    make_organizer(tmp_path, compile=True).organize('archive')
    assert not rs.path_for(tmp_path).exists()
    write_parts(tmp_path, {'riser2.othd': othd(range(5, 11))})
    make_organizer(tmp_path, compile=True, dry_run=True).organize('archive')
    assert not rs.path_for(tmp_path).exists()


def test_restarts_file_reads_with_numpy(tmp_path):
    import numpy as np
    write_parts(tmp_path, {'riser1.othd': othd(range(1, 8)), 'riser2.othd': othd(range(5, 11))})
    make_organizer(tmp_path, compile=True).organize('archive')
    after, first, t = np.loadtxt(rs.path_for(tmp_path), usecols=(0, 1, 2), ndmin=2).T
    assert list(after) == [4] and list(first) == [5] and t[0] == pytest.approx(0.25)
