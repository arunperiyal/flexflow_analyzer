import pytest
from src.core import history


def test_parse_runs_lists_and_ranges():
    assert history.parse_runs('1') == [1]
    assert history.parse_runs('1,3-5') == [1, 3, 4, 5]
    assert history.parse_runs('2-4') == [2, 3, 4]


@pytest.mark.parametrize('text', ['', '1,,2', 'a', '0', '3,1', '1,1', '2-1', '1-3,2', '-2'])
def test_parse_runs_refuses(text):
    with pytest.raises(ValueError):
        history.parse_runs(text)


def test_pick_archived(tmp_path):
    arch = tmp_path / 'othd_files' / 'archive'
    arch.mkdir(parents=True)
    for n in (1, 2, 6):
        (arch / f'riser{n}.othd').write_text('x')
    got = history.pick_archived(tmp_path, 'othd', 'riser', [2, 6])
    assert [p.name for p in got] == ['riser2.othd', 'riser6.othd']
    assert len(history.pick_archived(tmp_path, 'othd', 'riser', None)) == 3
    with pytest.raises(ValueError, match='run 3.*there: 1, 2, 6'):
        history.pick_archived(tmp_path, 'othd', 'riser', [3])


def _case(tmp_path, archive=(), cleaned=()):
    for sub, numbers in (('archive', archive), ('cleaned', cleaned)):
        d = tmp_path / 'othd_files' / sub
        d.mkdir(parents=True, exist_ok=True)
        for n in numbers:
            (d / f'riser{n}.othd').write_text(f'{sub}{n}')
    return tmp_path


def _names(case):
    return {n: p.read_text() for n, p in history.runs(case, 'othd', 'riser').items()}


def test_no_record_means_cleaned_n_is_archive_n(tmp_path):
    case = _case(tmp_path, archive=(1, 2), cleaned=(1, 2, 3))
    assert _names(case) == {1: 'archive1', 2: 'archive2', 3: 'cleaned3'}
    assert history.selection(case, 'othd') == {}
    assert history.skipped(case, 'othd', 'riser') == []


def test_record_roundtrip_and_removal(tmp_path):
    case = _case(tmp_path)
    history.write_selection(case, 'othd', {1: 1, 2: 2, 3: 6})
    assert history.selection(case, 'othd') == {1: 1, 2: 2, 3: 6}
    history.write_selection(case, 'othd', {})
    assert history.selection(case, 'othd') == {}
    assert not history.record_path(case, 'othd').exists()


def test_a_broken_record_is_no_record(tmp_path):
    case = _case(tmp_path, cleaned=(1,))
    history.record_path(case, 'othd').write_text('{not json')
    assert history.selection(case, 'othd') == {}


def test_a_selection_renames_and_skips(tmp_path):
    # archive 1..6; cleaned holds 1,2,3 = archive 1,2,6; runs 3,4,5 are not in it
    case = _case(tmp_path, archive=(1, 2, 3, 4, 5, 6), cleaned=(1, 2, 3))
    history.write_selection(case, 'othd', {1: 1, 2: 2, 3: 6}, skipped=[3, 4, 5])
    assert history.skipped(case, 'othd', 'riser') == [3, 4, 5]
    assert _names(case) == {1: 'archive1', 2: 'archive2', 6: 'archive6'}


def test_a_cleaned_file_stands_for_its_source_run(tmp_path):
    # archive 1..6 present; cleaned 3 is archive 6's steps -- never archive 3's
    case = _case(tmp_path, archive=(1, 2, 6), cleaned=(1, 2, 3))
    history.write_selection(case, 'othd', {1: 1, 2: 2, 3: 6}, skipped=[3])
    assert _names(case) == {1: 'archive1', 2: 'archive2', 6: 'archive6'}
    for p in (case / 'othd_files' / 'archive').glob('*'):
        p.unlink()
    assert _names(case) == {1: 'cleaned1', 2: 'cleaned2', 6: 'cleaned3'}


def test_a_newer_archive_run_is_a_new_run(tmp_path):
    # --clean 1,3 left run 2 out; runs 4 and 7 came after the record
    case = _case(tmp_path, archive=(1, 2, 3, 4, 7), cleaned=(1, 2))
    history.write_selection(case, 'othd', {1: 1, 2: 3}, skipped=[2])
    assert history.skipped(case, 'othd', 'riser') == [2]
    assert sorted(_names(case)) == [1, 3, 4, 7]


def test_runs_above_the_selection_can_be_skipped_too(tmp_path):
    # --clean 1,2,3 of an archive 1..6 leaves 4,5,6 out
    case = _case(tmp_path, archive=(1, 2, 3, 4, 5, 6), cleaned=(1, 2, 3))
    history.write_selection(case, 'othd', {1: 1, 2: 2, 3: 3}, skipped=[4, 5, 6])
    assert sorted(_names(case)) == [1, 2, 3]
