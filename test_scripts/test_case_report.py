"""`case report`: the last step of each case, read from the end of its .othd
files rather than parsing them whole."""

from pathlib import Path

from src.commands.case.report_impl import command as report


def othd(path, ts_ids, nodes=1):
    rows = ''.join(f"tsId {t}\ntime {t * 0.05}\n" + "0.1 0.2 0.3\n" * nodes for t in ts_ids)
    path.write_text("mask 455\nnOths 1\n" + rows)
    return path


def test_last_tsid_reads_the_tail(tmp_path):
    assert report._last_tsid(othd(tmp_path / 'a.othd', range(1, 5001))) == 5000
    # a restart inside the file: where the restarted run stopped
    assert report._last_tsid(othd(tmp_path / 'b.othd', [1, 2, 3, 4, 2, 3])) == 3
    assert report._last_tsid(othd(tmp_path / 'c.othd', [])) is None


def test_last_tsid_with_blocks_bigger_than_the_first_window(tmp_path):
    # ~1.2 MB per step: the first 1 MB window holds no tsId line at all
    assert report._last_tsid(othd(tmp_path / 'wide.othd', [7, 8, 9], nodes=100_000)) == 9


def test_last_timestep_across_parts(tmp_path):
    othd(tmp_path / 'riser1.othd', range(1, 101))
    othd(tmp_path / 'riser2.othd', range(90, 151))
    othd(tmp_path / 'riser3.othd', range(20, 41))
    assert report._last_othd_timestep_in_dir(tmp_path) == 150
    assert report._last_othd_timestep_in_dir(tmp_path / 'nope') is None
