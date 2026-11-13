"""core/chain.py: what stands in for a file so that it may be deleted.
.out <- ASCII PLT <- binary PLT <- the copy on the remote; a missing link is
passed over, and "written after" guards against a restart."""

import os

import pytest

from src.core.chain import Chain, RemoteCopies
from test_scripts.plt_files import write_ascii_plt, write_plt

T0 = 1_700_000_000


def at(path, seconds):
    os.utime(path, (T0 + seconds, T0 + seconds))
    return path


@pytest.fixture
def case(tmp_path):
    case = tmp_path / 'CS1'
    (case / 'RUN_1').mkdir(parents=True)
    (case / 'binary').mkdir()
    return case


def outs(case, step, when=0):
    paths = [case / 'RUN_1' / f'riser.{step}_{k}.out' for k in range(2)]
    for p in paths:
        p.write_text('out')
        at(p, when)
    return paths


def ascii_plt(case, step, when):
    return at(write_ascii_plt(case / 'RUN_1' / f'riser.{step}.plt'), when)


def binary_plt(case, step, when, **kw):
    return at(write_plt(case / 'binary' / f'riser.{step}.plt', **kw), when)


def remote(good=None, verified=(), problem=None):
    return RemoteCopies(lambda: ({s: T0 + t for s, t in (good or {}).items()},
                                 set(verified), problem))


def chain(case, **kw):
    return Chain(case, 'riser', case / 'RUN_1', **kw)


# --- .out ----------------------------------------------------------------------------

def test_out_stands_on_a_whole_newer_ascii_plt(case):
    ascii_plt(case, 100, 10)
    s = chain(case).for_out(100, outs(case, 100))
    assert s.ok and s.by == 'ascii'


def test_out_with_an_ascii_plt_cut_short_or_older_falls_to_nothing(case):
    p = ascii_plt(case, 100, 10)
    p.write_text(p.read_text()[:-20])
    at(p, 10)
    s = chain(case).for_out(100, outs(case, 100))
    assert not s.ok and s.found and 'cut short' in s.why
    ascii_plt(case, 200, 10)
    s = chain(case).for_out(200, outs(case, 200, when=20))       # a restart wrote the .out again
    assert not s.ok and 'older than its .out' in s.why


def test_a_good_binary_covers_the_out_whatever_the_ascii_is_like(case):
    p = ascii_plt(case, 100, 10)
    p.write_text('TITLE\n')
    binary_plt(case, 100, 30)
    s = chain(case).for_out(100, outs(case, 100))
    assert s.ok and s.by == 'binary'


def test_out_with_no_ascii_stands_on_the_binary_then_on_the_remote(case):
    binary_plt(case, 100, 30)
    assert chain(case).for_out(100, outs(case, 100)).by == 'binary'
    s = chain(case, remote=remote(good={200: 30})).for_out(200, outs(case, 200))
    assert s.ok and s.by == 'remote'
    # the copy on the remote was made before the restart wrote the .out again
    s = chain(case, remote=remote(good={300: 30})).for_out(300, outs(case, 300, when=40))
    assert not s.ok and 'not newer' in s.why


def test_out_with_a_binary_cut_short_does_not_look_at_the_remote(case):
    binary_plt(case, 100, 30, cut=40)
    s = chain(case, remote=remote(good={100: 30})).for_out(100, outs(case, 100))
    assert not s.ok and 'binary/riser.100.plt is' in s.why


def test_out_with_nothing_after_it(case):
    s = chain(case, remote=remote()).for_out(100, outs(case, 100))
    assert not s.ok and not s.found and 'no riser.100.plt anywhere' in s.why
    s = chain(case).for_out(100, outs(case, 100))                # no remote given
    assert not s.ok and not s.found and 'the remote was not asked' in s.why


# --- ASCII PLT -----------------------------------------------------------------------

def test_ascii_stands_on_a_whole_binary_written_after_it(case):
    ascii_plt(case, 100, 10)
    binary_plt(case, 100, 20)
    assert chain(case).for_ascii(100).by == 'binary'
    ascii_plt(case, 200, 10)
    binary_plt(case, 200, 10)                                    # same age: not after
    assert not chain(case).for_ascii(200).ok
    ascii_plt(case, 300, 10)
    binary_plt(case, 300, 20, cut=40)
    s = chain(case).for_ascii(300)
    assert not s.ok and s.found


def test_ascii_with_no_binary_here_stands_on_the_remote_copy(case):
    ascii_plt(case, 100, 10)
    assert chain(case, remote=remote(good={100: 20})).for_ascii(100).by == 'remote'
    s = chain(case, remote=remote(good={100: 5})).for_ascii(100)
    assert not s.ok and 'not newer' in s.why
    s = chain(case, remote=remote()).for_ascii(100)
    assert not s.ok and not s.found and s.why == 'no binary PLT here or on the remote'
    s = chain(case, remote=remote(problem='cannot log in')).for_ascii(100)
    assert not s.ok and 'cannot log in' in s.why


# --- binary PLT ----------------------------------------------------------------------

def test_binary_stands_only_on_a_copy_checked_just_now(case):
    binary_plt(case, 100, 20)
    assert chain(case, remote=remote(good={100: 20}, verified={100})).for_binary(100).ok
    # as the ledger recorded it, but not compared with this file now: not enough
    assert not chain(case, remote=remote(good={100: 20})).for_binary(100).ok
    s = chain(case).for_binary(100)
    assert not s.ok and '--remote' in s.why


def test_the_remote_is_asked_once_and_only_when_needed(case):
    calls = []

    def load():
        calls.append(1)
        return {200: T0 + 30}, set(), None

    c = Chain(case, 'riser', case / 'RUN_1', remote=RemoteCopies(load))
    binary_plt(case, 100, 30)
    c.for_out(100, outs(case, 100))                              # the binary is here
    assert calls == []
    c.for_out(200, outs(case, 200))
    c.for_out(300, outs(case, 300))
    assert calls == [1]
