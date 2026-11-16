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
