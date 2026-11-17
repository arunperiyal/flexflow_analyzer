"""`case organise history --clean 1,2,4`: clean only those archive runs.

archive/ is the store and is never changed. cleaned/ is derived, so a
selection replaces it: the named runs are written as riser1..N in the order
given, whatever cleaned/ held before is removed, and cleaned/.runs.json says
which archive run each file came from.
"""

import json

import pytest

from src.core import history
from test_case_organise_history import archive, names, othd, run, values

RUNS = {'riser1.othd': othd(range(1, 7), 1.0),
        'riser2.othd': othd(range(5, 11), 2.0),      # restart from 4
        'riser3.othd': othd(range(9, 15), 3.0),      # an abandoned branch
        'riser4.othd': othd(range(9, 17), 4.0),      # the run that went on
        'riser5.othd': othd(range(17, 21), 5.0)}

CLEANED = 'othd_files/cleaned'


def cleaned(case):
    return case / CLEANED


@pytest.fixture
def case(tmp_path):
    archive(tmp_path, RUNS)
    return tmp_path


def test_a_selection_replaces_cleaned_and_renames_in_order(case):
    run(case, clean=True)
    assert names(cleaned(case)) == ['riser1.othd', 'riser2.othd', 'riser4.othd', 'riser5.othd']

    run(case, clean='1,2,4')

    assert names(cleaned(case)) == ['.runs.json', 'riser1.othd', 'riser2.othd', 'riser3.othd']
    assert values(cleaned(case) / 'riser1.othd') == {t: 1.0 for t in range(1, 5)}
    assert values(cleaned(case) / 'riser2.othd') == {t: 2.0 for t in range(5, 9)}
    assert values(cleaned(case) / 'riser3.othd') == {t: 4.0 for t in range(9, 17)}   # archive 4
    record = json.loads((cleaned(case) / '.runs.json').read_text())
    assert record == {'cleaned': {'1': 1, '2': 2, '3': 4}, 'skipped': [3, 5]}
    assert history.selection(case, 'othd') == {1: 1, 2: 2, 3: 4}
    assert names(case / 'othd_files' / 'archive') == sorted(RUNS)      # untouched


def test_the_output_shows_the_mapping(case):
    _, out = run(case, clean='1,2,4')
    assert 'riser3.othd ← archive 4' in out
    assert 'riser1.othd ← archive 1' in out


def test_a_gap_between_the_chosen_runs_is_reported(case):
    _, out = run(case, clean='1,5')
    assert 'in none of these runs' in out


def test_descending_or_repeated_runs_change_nothing(case):
    run(case, clean=True)
    before = names(cleaned(case))
    for text in ('4,1', '1,1'):
        _, out = run(case, clean=text)
        assert 'ascending' in out
    assert names(cleaned(case)) == before


def test_a_run_not_in_archive_changes_nothing(case):
    run(case, clean=True)
    before = names(cleaned(case))
    _, out = run(case, clean='1,9')
    assert 'no run 9' in out and 'there: 1, 2, 3, 4, 5' in out
    assert names(cleaned(case)) == before
    assert not (cleaned(case) / '.runs.json').exists()


def test_dry_run_writes_nothing(case):
    run(case, clean=True)
    before = {p.name: p.read_text() for p in cleaned(case).iterdir()}
    run(case, clean='1,2,4', dry_run=True)
    assert {p.name: p.read_text() for p in cleaned(case).iterdir()} == before


def test_the_same_selection_again_is_up_to_date(case):
    run(case, clean='1,2,4')
    _, out = run(case, clean='1,2,4')
    assert 'cleaned/ is up to date' in out


def test_readers_follow_the_selection(case):
    run(case, clean='1,2,4')
    assert sorted(history.runs(case, 'othd', 'riser')) == [1, 2, 4]    # 3 and 5 are left out
    assert history.skipped(case, 'othd', 'riser') == [3, 5]
    archive(case, {'riser6.othd': othd(range(17, 21), 6.0)})           # a job after the clean
    assert sorted(history.runs(case, 'othd', 'riser')) == [1, 2, 4, 6]


def test_compile_and_verify_after_a_selection(case):
    organizer, _ = run(case, clean='1,2,4', compile=True, verify=True)
    assert organizer.stats['verify_ok']
    compiled = case / 'othd_files' / 'riser.othd'
    assert sorted(values(compiled)) == list(range(1, 17))
    assert values(compiled)[9] == 4.0 and values(compiled)[6] == 2.0
    # and again, separately: still up to date
    organizer, _ = run(case, verify=True)
    assert organizer.stats['verify_ok']


def test_a_plain_clean_drops_the_selection(case):
    run(case, clean='1,2,4')
    run(case, clean=True)
    assert not (cleaned(case) / '.runs.json').exists()
    assert names(cleaned(case)) == ['riser1.othd', 'riser2.othd', 'riser4.othd', 'riser5.othd']
    assert history.selection(case, 'othd') == {}


def test_both_kinds_follow_the_same_selection(case):
    archive(case, {n.replace('othd', 'oisd'): t for n, t in RUNS.items()}, ext='oisd')
    run(case, clean='1,2,4')
    for ext in ('othd', 'oisd'):
        assert history.selection(case, ext) == {1: 1, 2: 2, 3: 4}
        assert names(case / f'{ext}_files' / 'cleaned') == [
            '.runs.json', f'riser1.{ext}', f'riser2.{ext}', f'riser3.{ext}']
