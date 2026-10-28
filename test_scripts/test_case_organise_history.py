"""Tests for `case organise history`.

    othd_files/archive/riserN.othd   as job N wrote it (--update, mainFlex.sh)
    othd_files/cleaned/riserN.othd   run N without the steps later runs redid (--clean)
    othd_files/riser.othd            cleaned/ joined (--compile)

A restart reruns timesteps already written, so a tsId at or below one already
taken drops everything from there on in favour of the later run -- the later
N, the same rule the readers apply in name order. --prune deletes archive/
only when cleaned/ holds it; later runs are then cleaned against cleaned/.
"""

import io
import os
import subprocess
import time
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.console import Console

from src.commands.case.organise_impl.organizer import CaseOrganizer
from src.core import history
from src.core.readers.othd_reader import OTHDReader

HEADER = "mask 455\nnOths 1\n"
ROOT = Path(__file__).resolve().parent.parent


def othd(ts_ids, value=0.0, header=HEADER):
    """A one-node OTHD whose displacement records which run a step came from."""
    blocks = "".join(f"tsId {t}\ntime {t * 0.05}\nothId 0\naleDisp 3 1\n"
                     f"{value} {t} 0.0\n" for t in ts_ids)
    return header + blocks


class _Logger:
    def __getattr__(self, name):
        return lambda *a, **k: None


def make_organizer(case_dir, **flags):
    args = Namespace(update=False, verify=False, clean=False, compile=False, prune=False,
                     dry_run=False, no_confirm=False, log=False, verbose=False, t1=None, t2=None)
    for key, value in flags.items():
        setattr(args, key, value)
    case = SimpleNamespace(case_directory=str(case_dir), problem_name='riser',
                           config={'dir': './RUN_1'})
    return CaseOrganizer(case, args, _Logger(), Console(file=io.StringIO(), width=200))


def run(case_dir, **flags):
    organizer = make_organizer(case_dir, **flags)
    organizer.organize('history')
    return organizer, ' '.join(organizer.console.file.getvalue().split())


def archive(case_dir, parts, ext='othd'):
    d = case_dir / f'{ext}_files' / 'archive'
    d.mkdir(parents=True, exist_ok=True)
    for name, text in parts.items():
        (d / name).write_text(text)
    return d


def names(directory):
    return sorted(p.name for p in directory.iterdir()) if directory.exists() else []


def values(path):
    """{tsId: run value} of an OTHD written by othd()."""
    out, ts = {}, None
    for line in Path(path).read_text().splitlines():
        if line.startswith('tsId '):
            ts = int(line.split()[1])
        elif ts is not None and (line[:1].isdigit() or line[:1] == '-'):
            out[ts] = float(line.split()[0])
    return out


RESTARTED = {'riser1.othd': othd(range(1, 8), value=1.0),
             'riser2.othd': othd(range(5, 11), value=2.0)}       # restart from 4


# --- --update and the old layout -------------------------------------------------

def test_update_moves_the_run_to_the_next_number(tmp_path):
    archive(tmp_path, {'riser1.othd': othd([1, 2])})
    cleaned = tmp_path / 'othd_files' / 'cleaned'
    cleaned.mkdir()
    (cleaned / 'riser3.othd').write_text(othd([3]))           # archive/riser3 pruned
    run_dir = tmp_path / 'RUN_1'
    run_dir.mkdir()
    for ext in ('othd', 'oisd', 'rcv'):
        (run_dir / f'riser.{ext}').write_text(othd([4, 5]))
    run(tmp_path, update=True)
    assert names(run_dir) == []
    assert names(tmp_path / 'othd_files' / 'archive') == ['riser1.othd', 'riser4.othd']
    assert names(tmp_path / 'oisd_files' / 'archive') == ['riser4.oisd']
    assert names(tmp_path / 'rcv_files') == ['riser4.rcv']


def test_flat_parts_move_into_archive_keeping_runs_together(tmp_path):
    archive(tmp_path, {'riser2.othd': othd([3])})
    flat = tmp_path / 'othd_files'
    (flat / 'riser1.othd').write_text(othd([1]))
    (flat / 'riser2.othd').write_text(othd([4]))              # an old job script's: number taken
    (tmp_path / 'oisd_files').mkdir()
    (tmp_path / 'oisd_files' / 'riser2.oisd').write_text(othd([4]))
    run(tmp_path, verify=True)
    assert names(flat) == ['archive']
    assert names(flat / 'archive') == ['riser1.othd', 'riser2.othd', 'riser3.othd']
    assert (flat / 'archive' / 'riser3.othd').read_text() == othd([4])
    assert names(tmp_path / 'oisd_files' / 'archive') == ['riser3.oisd']


# --- --clean ---------------------------------------------------------------------

def test_clean_cuts_each_run_where_the_next_one_took_over(tmp_path):
    archive(tmp_path, RESTARTED)
    organizer, out = run(tmp_path, clean=True)
    cleaned = tmp_path / 'othd_files' / 'cleaned'
    assert values(cleaned / 'riser1.othd') == {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}
    assert values(cleaned / 'riser2.othd') == {t: 2.0 for t in range(5, 11)}
    assert '3 redone by later runs' in out
    assert (tmp_path / '.restarts').exists()
    assert names(tmp_path / 'othd_files' / 'archive') == ['riser1.othd', 'riser2.othd']


def test_clean_follows_the_run_number_not_the_first_tsid(tmp_path):
    # run 3 restarted from 4000-ish before run 2's start: run 3 still wins
    archive(tmp_path, {'riser1.othd': othd(range(1, 11), 1.0),
                       'riser2.othd': othd(range(6, 15), 2.0),
                       'riser3.othd': othd(range(4, 8), 3.0)})
    run(tmp_path, clean=True)
    cleaned = tmp_path / 'othd_files' / 'cleaned'
    assert names(cleaned) == ['riser1.othd', 'riser3.othd']    # run 2 entirely redone
    assert values(cleaned / 'riser3.othd') == {t: 3.0 for t in range(4, 8)}


def test_clean_leaves_out_a_cut_off_last_step(tmp_path):
    archive(tmp_path, {'riser1.othd': othd([1, 2, 3])[:-12]})
    _, out = run(tmp_path, clean=True)
    assert sorted(values(tmp_path / 'othd_files' / 'cleaned' / 'riser1.othd')) == [1, 2]
    assert 'last step (tsId 3) cut off — left out' in out


def test_clean_stops_on_a_damaged_middle_step(tmp_path):
    text = othd([1, 2, 3]).replace('0.0 2 0.0', '1.2.3 2 0.0')
    archive(tmp_path, {'riser1.othd': text})
    _, out = run(tmp_path, clean=True, compile=True)
    assert not (tmp_path / 'othd_files' / 'cleaned').exists()
    assert 'non-numeric values (tsId 2)' in out and 'fix or remove it first' in out


def test_clean_twice_changes_nothing(tmp_path):
    archive(tmp_path, RESTARTED)
    run(tmp_path, clean=True)
    _, out = run(tmp_path, clean=True)
    assert 'cleaned/ is up to date' in out


# --- --compile and the readers ------------------------------------------------------

def test_compile_joins_cleaned_and_the_readers_take_it(tmp_path):
    archive(tmp_path, RESTARTED)
    run(tmp_path, clean=True, compile=True)
    compiled = tmp_path / 'othd_files' / 'riser.othd'
    assert values(compiled) == {**{t: 1.0 for t in range(1, 5)}, **{t: 2.0 for t in range(5, 11)}}
    assert history.read_files(tmp_path, 'othd', 'riser') == [compiled]
    assert OTHDReader([str(compiled)]).tsIds == list(range(1, 11))


def test_readers_fall_back_to_the_runs_once_archive_changes(tmp_path):
    archive(tmp_path, RESTARTED)
    run(tmp_path, clean=True, compile=True)
    later = time.time() + 5
    new = tmp_path / 'othd_files' / 'archive' / 'riser3.othd'
    new.write_text(othd([11, 12], value=3.0))
    os.utime(new, (later - 60, later - 60))     # moved in: keeps an old mtime...
    os.utime(new.parent, (later, later))        # ...but the directory changed
    files = history.read_files(tmp_path, 'othd', 'riser')
    assert [p.name for p in files] == ['riser1.othd', 'riser2.othd', 'riser3.othd']
    assert all(p.parent.name == 'archive' for p in files)


def test_compile_refuses_a_cleaned_out_of_date(tmp_path):
    archive(tmp_path, RESTARTED)
    run(tmp_path, clean=True)
    archive(tmp_path, {'riser3.othd': othd([11], value=3.0)})
    _, out = run(tmp_path, compile=True)
    assert not (tmp_path / 'othd_files' / 'riser.othd').exists()
    assert 'run --clean first' in out


# --- --verify ----------------------------------------------------------------------

def test_verify_accepts_a_clean_history(tmp_path):
    archive(tmp_path, RESTARTED)
    organizer, out = run(tmp_path, clean=True, compile=True, verify=True)
    assert organizer.stats['verify_ok'] is True and 'problems' not in out


def test_verify_notes_a_cut_off_archive_step_without_failing(tmp_path):
    archive(tmp_path, {'riser1.othd': othd([1, 2, 3])[:-12]})
    organizer, out = run(tmp_path, clean=True, verify=True)
    assert organizer.stats['verify_ok'] is True
    assert 'incomplete last step (tsId 3) — --clean leaves it out' in out


def test_verify_fails_cleaned_and_compiled_out_of_date(tmp_path):
    archive(tmp_path, RESTARTED)
    run(tmp_path, clean=True, compile=True)
    archive(tmp_path, {'riser3.othd': othd([9, 10, 11], value=3.0)})
    organizer, out = run(tmp_path, verify=True)
    assert organizer.stats['verify_ok'] is False
    assert 'cleaned/riser2.othd' in out and 'out of date with archive/ — run --clean' in out
    assert 'cleaned/riser3.othd │ — │ — │ missing — run --clean' in out

    run(tmp_path, clean=True)
    organizer, out = run(tmp_path, verify=True)
    assert organizer.stats['verify_ok'] is False
    assert 'not cleaned/ joined — run --compile' in out


def test_verify_reports_tsids_in_no_run_without_failing(tmp_path):
    # the second run restarted from 15 while the first only reached 10
    archive(tmp_path, {'riser1.othd': othd(range(1, 11)), 'riser2.othd': othd(range(15, 20))})
    organizer, out = run(tmp_path, clean=True, compile=True, verify=True)
    assert organizer.stats['verify_ok'] is True
    assert organizer.stats['verify_lost'] == 4
    assert 'OTHD: 4 tsId(s) in no run (11 – 14)' in out


# --- --prune -------------------------------------------------------------------------

def test_prune_deletes_archive_once_cleaned_holds_it(tmp_path):
    archive(tmp_path, RESTARTED)
    run(tmp_path, clean=True, compile=True, verify=True, prune=True, no_confirm=True)
    assert names(tmp_path / 'othd_files' / 'archive') == []
    assert names(tmp_path / 'othd_files' / 'cleaned') == ['riser1.othd', 'riser2.othd']
    assert values(tmp_path / 'othd_files' / 'riser.othd')[10] == 2.0
    # the readers keep the compiled file: pruning did not change the history
    assert history.read_files(tmp_path, 'othd', 'riser') == [tmp_path / 'othd_files' / 'riser.othd']


def test_prune_refuses_a_cleaned_out_of_date(tmp_path):
    archive(tmp_path, RESTARTED)
    run(tmp_path, clean=True)
    archive(tmp_path, {'riser3.othd': othd([11], value=3.0)})
    _, out = run(tmp_path, prune=True, no_confirm=True)
    assert len(names(tmp_path / 'othd_files' / 'archive')) == 3
    assert 'nothing pruned' in out


def test_after_a_prune_a_later_run_is_cleaned_against_cleaned(tmp_path, monkeypatch):
    archive(tmp_path, RESTARTED)
    run(tmp_path, clean=True, prune=True, no_confirm=True)
    archive(tmp_path, {'riser3.othd': othd(range(9, 13), value=3.0)})   # restart from 8

    # cleaned/riser2 is now the only copy of run 2: cutting it asks
    monkeypatch.setattr('builtins.input', lambda *a: 'n')
    run(tmp_path, clean=True)
    assert max(values(tmp_path / 'othd_files' / 'cleaned' / 'riser2.othd')) == 10

    monkeypatch.setattr('builtins.input', lambda *a: 'y')
    run(tmp_path, clean=True, compile=True)
    joined = values(tmp_path / 'othd_files' / 'riser.othd')
    assert sorted(joined) == list(range(1, 13))
    assert [joined[4], joined[8], joined[9]] == [1.0, 2.0, 3.0]


# --- mainFlex.sh ---------------------------------------------------------------------

def test_mainflex_archives_the_run_one_past_every_kept_number(tmp_path):
    script = (ROOT / 'src' / 'templates' / 'scripts' / 'mainFlex.sh').read_text()
    step = script[script.index('mkdir -p othd_files/archive'):script.index('# Auto-restart')]
    for d in ('RUN_1', 'othd_files/cleaned', 'oisd_files'):
        (tmp_path / d).mkdir(parents=True)
    (tmp_path / 'othd_files' / 'cleaned' / 'riser3.othd').write_text('')
    (tmp_path / 'othd_files' / 'riser5.othd').write_text('')       # old layout
    (tmp_path / 'othd_files' / 'riser.othd').write_text('')        # compiled: no number
    (tmp_path / 'RUN_1' / 'riser.othd').write_text('x')
    (tmp_path / 'RUN_1' / 'riser.oisd').write_text('x')
    r = subprocess.run(['bash', '-c', step], cwd=tmp_path, capture_output=True, text=True,
                       env={**os.environ, 'PROBLEM': 'riser', 'RUN_DIR': 'RUN_1'})
    assert 'Archived run 6' in r.stdout, r.stderr
    assert names(tmp_path / 'othd_files' / 'archive') == ['riser6.othd']
    assert names(tmp_path / 'oisd_files' / 'archive') == ['riser6.oisd']
