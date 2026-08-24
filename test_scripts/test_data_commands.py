"""Tests for `data show`, `data table` and `data stats`, and the `*` wildcard
they share through `shared.for_each_case`.

The bug: all three resolved `args.case` straight to a directory, so `*` --
meant everywhere else in the app as "every case in the .cases registry" --
came out as `Case directory not found: *`. `shared.for_each_case` is the one
place that now decides between the two, and each command's own body only ever
sees a real case directory, exactly as it always did for a single case.
"""

import json

import pytest

from src.commands.data import shared
from src.commands.data.show_impl.command import execute_preview
from src.commands.data.table_impl.command import execute_table
from src.commands.data.stats_impl.command import execute_statistics


def _othd_text(n_steps=20):
    """A tiny, real othd: one nodal block, two nodes, a signal that crosses
    zero both ways -- two full periods, so `zeroloc` has both an ascending
    and a descending crossing to find, not just a single upward wiggle."""
    import math
    lines = []
    for i in range(1, n_steps + 1):
        t = i * 0.1
        v0 = math.sin(2 * math.pi * t / (n_steps * 0.1) * 2)
        v1 = 2.0 * v0
        lines += [f"tsId {i}", f"time {t:.10f}", "othId 0", "othFlag 1",
                 "aleDisp 3 2",
                 f"{v0:.10f} 0.0 0.0",
                 f"{v1:.10f} 0.0 0.0"]
    return "\n".join(lines) + "\n"


def _make_case(root, name, n_steps=5, out_freq=1):
    d = root / name
    (d / "othd_files").mkdir(parents=True)
    (d / "othd_files" / "riser1.othd").write_text(_othd_text(n_steps))
    (d / "simflow.config").write_text(f"problem = riser\nnp = 1\noutFreq = {out_freq}\n")
    return d


def args(**over):
    """An args Namespace with every flag `data show`/`table`/`stats` read."""
    base = dict(case=None, verbose=False, help=False, examples=False,
                othd=False, oisd=False, var=None, func=None, t1=None, t2=None,
                node=None, group=None, output=None, head=None, tail=None)
    base.update(over)
    import argparse
    return argparse.Namespace(**base)


class _Logger:
    """Stands in for utils.Logger: error/warning to stderr, info/success silent."""

    def error(self, msg):
        import sys
        print(msg, file=sys.stderr)

    def warning(self, msg):
        import sys
        print(msg, file=sys.stderr)

    def info(self, msg):
        pass

    def success(self, msg):
        pass


@pytest.fixture
def case(tmp_path):
    """One real case, for checking the ordinary single-case path is unchanged."""
    return _make_case(tmp_path, "OnlyCase")


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """.cases mixing two real cases and one whose directory is gone."""
    _make_case(tmp_path, "Good1")
    _make_case(tmp_path, "Good2")
    entries = [{"name": "Good1", "path": str(tmp_path / "Good1")},
              {"name": "Good2", "path": str(tmp_path / "Good2")},
              {"name": "Gone", "path": str(tmp_path / "not_here")}]
    (tmp_path / ".cases").write_text(json.dumps(entries))
    monkeypatch.chdir(tmp_path)          # .cases is read from the cwd
    return tmp_path


def flat(text):
    """Strip rich's colour codes so assertions can match on plain substrings."""
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestForEachCase:
    """shared.for_each_case in isolation, with a stub run_one -- no real case
    data needed for the iteration logic itself."""

    def test_single_case_delegates_directly(self, case):
        seen = []
        shared.for_each_case(args(case=str(case)), _Logger(),
                             lambda d, a: seen.append(d))
        assert seen == [case]

    def test_single_case_propagates_its_own_systemexit(self, case):
        def boom(d, a):
            raise SystemExit(1)
        with pytest.raises(SystemExit):
            shared.for_each_case(args(case=str(case)), _Logger(), boom)

    def test_wildcard_visits_every_case_in_the_registry(self, registry):
        seen = []
        shared.for_each_case(args(case="*"), _Logger(),
                             lambda d, a: seen.append(d.name))
        assert set(seen) == {"Good1", "Good2"}

    def test_a_missing_case_directory_is_skipped_not_fatal(self, registry, capsys):
        seen = []
        shared.for_each_case(args(case="*"), _Logger(),
                             lambda d, a: seen.append(d.name))
        assert "Gone" not in seen
        assert "Good1" in seen and "Good2" in seen
        assert "case directory not found" in flat(capsys.readouterr().err)

    def test_one_bad_case_does_not_end_the_batch(self, registry, capsys):
        def run_one(d, a):
            if d.name == "Good1":
                raise SystemExit(1)

        shared.for_each_case(args(case="*"), _Logger(), run_one)
        out = flat(capsys.readouterr().out)
        assert "read 1/3 case" in out

    def test_exits_nonzero_when_nothing_succeeded(self, tmp_path, monkeypatch):
        (tmp_path / ".cases").write_text(json.dumps(
            [{"name": "Gone", "path": str(tmp_path / "not_here")}]))
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc:
            shared.for_each_case(args(case="*"), _Logger(), lambda d, a: None)
        assert exc.value.code == 1

    def test_empty_registry_errors(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc:
            shared.for_each_case(args(case="*"), _Logger(), lambda d, a: None)
        assert exc.value.code == 1

    def test_output_is_namespaced_per_case(self, registry):
        seen = {}
        shared.for_each_case(args(case="*", output="stats.csv"), _Logger(),
                             lambda d, a: seen.__setitem__(d.name, a.output))
        assert seen == {"Good1": "stats_Good1.csv", "Good2": "stats_Good2.csv"}

    def test_no_output_stays_none_per_case(self, registry):
        seen = []
        shared.for_each_case(args(case="*"), _Logger(),
                             lambda d, a: seen.append(a.output))
        assert seen == [None, None]

    def test_single_case_output_is_untouched(self, case):
        seen = []
        shared.for_each_case(args(case=str(case), output="stats.csv"), _Logger(),
                             lambda d, a: seen.append(a.output))
        assert seen == ["stats.csv"]


class TestDataShowWildcard:
    def test_star_reads_the_registry_not_a_directory_called_star(self, registry, capsys):
        """The bug: `data show *` took '*' as a literal path."""
        execute_preview(args(case="*"))
        captured = capsys.readouterr()
        out = flat(captured.out + captured.err)
        assert "Case directory not found: *" not in out

    def test_every_case_is_shown(self, registry, capsys):
        execute_preview(args(case="*"))
        out = flat(capsys.readouterr().out)
        assert "Good1" in out and "Good2" in out

    def test_single_case_still_works(self, case, capsys):
        execute_preview(args(case=str(case)))
        out = flat(capsys.readouterr().out)
        assert "OnlyCase" in out
        assert "aleDisp" in out


class TestDataTableWildcard:
    def test_star_reads_the_registry_not_a_directory_called_star(self, registry, capsys):
        execute_table(args(case="*", var=["aleDisp_x"]))
        captured = capsys.readouterr()
        out = flat(captured.out + captured.err)
        assert "Case directory not found: *" not in out

    def test_every_case_is_tabulated(self, registry, capsys):
        execute_table(args(case="*", var=["aleDisp_x"]))
        out = flat(capsys.readouterr().out)
        assert "Good1" in out and "Good2" in out

    def test_output_writes_one_csv_per_case(self, registry, tmp_path):
        execute_table(args(case="*", var=["aleDisp_x"], output="table.csv"))
        assert (tmp_path / "table_Good1.csv").exists()
        assert (tmp_path / "table_Good2.csv").exists()

    def test_single_case_still_works(self, case, capsys):
        execute_table(args(case=str(case), var=["aleDisp_x"]))
        out = flat(capsys.readouterr().out)
        assert "OnlyCase" in out


class TestDataStatsWildcard:
    """The exact bug reported: `data stats --func zeroloc/maxloc` under c:*."""

    def test_star_reads_the_registry_not_a_directory_called_star(self, registry, capsys):
        execute_statistics(args(case="*", var=["aleDisp_x"], func=["maxloc"]))
        captured = capsys.readouterr()
        out = flat(captured.out + captured.err)
        assert "Case directory not found: *" not in out

    def test_maxloc_over_every_case(self, registry, capsys):
        execute_statistics(args(case="*", var=["aleDisp_x"], func=["maxloc"]))
        out = flat(capsys.readouterr().out)
        assert "Good1" in out and "Good2" in out
        assert "maxloc" in out

    def test_zeroloc_over_every_case(self, registry, capsys):
        execute_statistics(args(case="*", var=["aleDisp_x"], func=["zeroloc"]))
        out = flat(capsys.readouterr().out)
        assert "Good1" in out and "Good2" in out
        assert "zeroloc" in out

    def test_a_missing_case_is_reported_and_the_rest_still_run(self, registry, capsys):
        execute_statistics(args(case="*", var=["aleDisp_x"], func=["max"]))
        captured = capsys.readouterr()
        assert "read 2/3 case" in flat(captured.out)
        assert "Gone" in flat(captured.err) or "not_here" in flat(captured.err)

    def test_bad_func_is_reported_once_before_touching_any_case(self, registry, capsys):
        """Not a per-case message: --func is validated before the loop starts."""
        with pytest.raises(SystemExit):
            execute_statistics(args(case="*", var=["aleDisp_x"], func=["bogus"]))
        err = flat(capsys.readouterr().err)
        assert err.count("unknown --func") == 1
        assert "Good1" not in err  # never got as far as opening a case

    def test_output_writes_one_csv_per_case(self, registry, tmp_path):
        execute_statistics(args(case="*", var=["aleDisp_x"], func=["max"],
                                output="stats.csv"))
        assert (tmp_path / "stats_Good1.csv").exists()
        assert (tmp_path / "stats_Good2.csv").exists()

    def test_single_case_still_works(self, case, capsys):
        execute_statistics(args(case=str(case), var=["aleDisp_x"], func=["max", "maxloc"]))
        out = flat(capsys.readouterr().out)
        assert "OnlyCase" in out
        assert "maxloc" in out
