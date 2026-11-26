"""case organise plt binary --no-verify: the remote is not asked."""

import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.console import Console

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.commands.case.organise_impl.organizer import CaseOrganizer
from src.core import chain
from plt_files import write_plt


class _Logger:
    def __getattr__(self, name):
        return lambda *a, **k: None


def organise(case_dir, out=None, **flags):
    args = Namespace(delete_ascii=False, delete_binary=True, freq=None, keep_freq=None,
                     dry_run=False, yes=True, log=False, verbose=False,
                     t1=None, t2=None, no_verify=False, remote=None)
    for key, value in flags.items():
        setattr(args, key, value)
    case = SimpleNamespace(case_directory=str(case_dir), problem_name='riser', config={})
    console = Console(file=out or open('/dev/null', 'w'), width=200)
    CaseOrganizer(case, args, _Logger(), console).organize('plt')


@pytest.fixture
def binary(tmp_path):
    d = tmp_path / 'binary'
    d.mkdir()
    for t in (10, 20):
        write_plt(d / f'riser.{t}.plt')
    write_plt(d / 'riser.30.plt', cut=40)      # cut short
    return d


@pytest.fixture
def asked(monkeypatch):
    calls = []
    monkeypatch.setattr(chain, 'remote_copies', lambda *a, **k: calls.append(1) or
                        chain.RemoteCopies(None))
    return calls


def test_without_the_flag_no_remote_deletes_nothing(tmp_path, binary, asked):
    organise(tmp_path)
    assert len(list(binary.glob('*.plt'))) == 3


def test_no_verify_deletes_whole_plts_without_asking_the_remote(tmp_path, binary, asked):
    import io
    out = io.StringIO()
    organise(tmp_path, out=out, no_verify=True)
    assert [p.name for p in binary.glob('*.plt')] == ['riser.30.plt']   # the cut one stays
    text = out.getvalue()
    assert 'not asked' in text and 'not checked' in text


def test_no_verify_dry_run_deletes_nothing(tmp_path, binary, asked):
    organise(tmp_path, no_verify=True, dry_run=True)
    assert len(list(binary.glob('*.plt'))) == 3


def test_the_chain_waives_only_the_binary_link(tmp_path, binary):
    c = chain.Chain(tmp_path, 'riser', None)
    ok = c.for_binary_unverified(10)
    assert ok.ok and ok.by == 'waived'
    cut = c.for_binary_unverified(30)
    assert not cut.ok and cut.found


def test_auto_never_passes_the_flag():
    for p in Path(__file__).parent.parent.joinpath('src/core/auto').glob('*.py'):
        assert '--no-verify' not in p.read_text(), p.name
