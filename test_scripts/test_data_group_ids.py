"""--othid and --osgid in `data table`/`data stats`.

othId numbers the probe sets in an othd, osgId the surface groups in an oisd;
the two numberings are unrelated. A single `group` context fed both, so
`use group:1` read othId 1 for an othd variable and an unrelated osgId 1 for
an oisd one. Each kind now takes its own id, picked by the kind the variables
live in; the other kind's id is ignored when it came from context and refused
when typed.
"""

import argparse
from types import SimpleNamespace

import pytest

import src.cli.context as context
from src.commands.data.table_impl.command import execute_table


def _two_group_case(root):
    """othId 0/1 and osgId 0/1, each group's values marking which it is."""
    othd, oisd = [], []
    for i in range(1, 4):
        othd += [f"tsId {i}", f"time {i * 0.1}"]
        oisd += [f"tsId {i}", f"time {i * 0.1}"]
        for g in (0, 1):
            othd += [f"othId {g}", "othFlag 1", "aleDisp 3 1", f"{10 + g}.0 0.0 0.0"]
            oisd += [f"osgId {g}", "osdFlag 1", f"totArea {20 + g}.0"]
    d = root / "Case"
    (d / "othd_files").mkdir(parents=True)
    (d / "oisd_files").mkdir()
    (d / "othd_files" / "riser1.othd").write_text("\n".join(othd) + "\n")
    (d / "oisd_files" / "riser1.oisd").write_text("\n".join(oisd) + "\n")
    (d / "simflow.config").write_text("problem = riser\nnp = 1\noutFreq = 1\n")
    return d


def args(case, var, **over):
    base = dict(case=str(case), verbose=False, help=False, examples=False,
                othd=False, oisd=False, var=[var], t1=None, t2=None, node=None,
                othid=None, osgid=None, group=None, output=None, head=None, tail=None)
    base.update(over)
    return argparse.Namespace(**base)


@pytest.fixture
def case(tmp_path):
    return _two_group_case(tmp_path)


def table(capsys, a):
    execute_table(a)
    return capsys.readouterr().out


def test_othid_reads_that_probe_set(case, capsys):
    out = table(capsys, args(case, "aleDisp", othid=1))
    assert "othId 1" in out and "1.100000e+01" in out


def test_osgid_reads_that_surface(case, capsys):
    out = table(capsys, args(case, "totArea", osgid=1))
    assert "osgId 1" in out and "2.100000e+01" in out


def test_group_still_works_for_either_kind(case, capsys):
    assert "osgId 1" in table(capsys, args(case, "totArea", group=1))
    assert "othId 1" in table(capsys, args(case, "aleDisp", group=1))


def test_typed_id_of_the_other_kind_is_refused(case, capsys):
    with pytest.raises(SystemExit):
        execute_table(args(case, "aleDisp", osgid=1))
    assert "--osgid picks a group in the oisd files" in capsys.readouterr().err


def test_context_id_of_the_other_kind_is_ignored(case, capsys, monkeypatch):
    # `use osgid:1` while tabulating an othd variable: not an error, not used.
    rt = SimpleNamespace(get=lambda key, default=None: {"osgid": 1}.get(key, default))
    monkeypatch.setattr(context, "current_runtime", lambda: rt)
    out = table(capsys, args(case, "aleDisp", osgid=1))
    assert "othId 0" in out and "1.000000e+01" in out


def test_group_and_own_id_must_agree(case, capsys):
    with pytest.raises(SystemExit):
        execute_table(args(case, "aleDisp", othid=0, group=1))
    assert "disagree" in capsys.readouterr().err
