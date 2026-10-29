"""`data table|stats --last N`: the last N steps of the history (of the
--t1/--t2 window), from `use last:N` too; and `data table --output` with no
file, which writes <case>/data_tables/<var>.csv."""

import argparse
import json

import numpy as np
import pytest

from src.commands.data import shared
from src.commands.data.stats_impl.command import execute_statistics
from src.commands.data.table_impl.command import execute_table


def _othd(n_steps):
    lines = []
    for i in range(1, n_steps + 1):
        lines += [f"tsId {i}", f"time {i * 0.1:.10f}", "othId 0", "othFlag 1",
                  "aleDisp 3 1", f"0.0 {i:.1f} 0.0"]
    return "\n".join(lines) + "\n"


def _case(root, name, n_steps=5):
    d = root / name
    (d / "othd_files").mkdir(parents=True)
    (d / "othd_files" / "riser1.othd").write_text(_othd(n_steps))
    (d / "simflow.config").write_text("problem = riser\nnp = 1\noutFreq = 1\n")
    return d


def args(**over):
    base = dict(case=None, verbose=False, help=False, examples=False, othd=False,
                oisd=False, var=None, func=None, t1=None, t2=None, node=None,
                group=None, output=None, head=None, tail=None, last=None)
    base.update(over)
    return argparse.Namespace(**base)


def tsids(path):
    return np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2)[:, 0].astype(int).tolist()


@pytest.fixture
def case(tmp_path):
    return _case(tmp_path, "CS1")


def test_last_keeps_the_highest_tsids(case, tmp_path):
    out = tmp_path / "t.csv"
    execute_table(args(case=str(case), var=["dy"], last=3, output=str(out)))
    assert tsids(out) == [3, 4, 5]


def test_last_is_of_the_window(case, tmp_path):
    out = tmp_path / "t.csv"
    execute_table(args(case=str(case), var=["dy"], t2=3, last=2, output=str(out)))
    assert tsids(out) == [2, 3]


def test_last_longer_than_the_history_takes_it_all(case, tmp_path):
    out = tmp_path / "t.csv"
    execute_table(args(case=str(case), var=["dy"], last=1000, output=str(out)))
    assert tsids(out) == [1, 2, 3, 4, 5]


def test_last_must_be_positive(case):
    with pytest.raises(SystemExit):
        execute_table(args(case=str(case), var=["dy"], last=0))


def test_last_steps_follows_tsid_not_file_order():
    mask = np.ones(4, dtype=bool)
    got = shared.last_steps(np.array([10, 40, 20, 30]), mask, 2, None)
    assert got.tolist() == [False, True, False, True]


def test_bare_output_writes_into_the_case(case):
    execute_table(args(case=str(case), var=["dy"], last=2, output=True))
    assert tsids(case / "data_tables" / "dy.csv") == [4, 5]


def test_bare_output_names_every_variable(case):
    execute_table(args(case=str(case), var=["dx,dy"], output=True))
    assert (case / "data_tables" / "dx_dy.csv").exists()


def test_bare_output_with_star_writes_into_each_case(tmp_path, monkeypatch):
    for name in ("A", "B"):
        _case(tmp_path, name)
    (tmp_path / ".cases").write_text(json.dumps(
        [{"name": n, "path": str(tmp_path / n)} for n in ("A", "B")]))
    monkeypatch.chdir(tmp_path)
    execute_table(args(case="*", var=["dy"], output=True))
    assert (tmp_path / "A/data_tables/dy.csv").exists()
    assert (tmp_path / "B/data_tables/dy.csv").exists()


def test_stats_takes_last(case, capsys):
    execute_statistics(args(case=str(case), var=["dy"], func=["mean"], last=2))
    out = capsys.readouterr().out
    assert "tsId 4..5 (2 steps)" in out and "4.5" in out


def test_reads_the_history_layout(tmp_path):
    case = _case(tmp_path, "CS2", n_steps=4)
    (case / "othd_files/archive").mkdir()
    (case / "othd_files/riser1.othd").rename(case / "othd_files/archive/riser1.othd")
    execute_table(args(case=str(case), var=["dy"], output=True))
    assert tsids(case / "data_tables/dy.csv") == [1, 2, 3, 4]
