"""Rules 4 and 6 of .claude/rules/command-design.md: flags are typed in full (no
abbreviations, on every parser), and a typed flag displaces the `use` values beside
it -- and says so -- while two typed flags that contradict each other are refused."""

import argparse
import io

import pytest
from rich.console import Console
from shellkit import Runtime
from shellkit.context import fill_context
from shellkit.parser import UsageError

from src.cli.app import create_app


@pytest.fixture
def rt(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    monkeypatch.chdir(tmp_path)
    out = io.StringIO()
    runtime = Runtime(create_app(), console=Console(file=out, width=200, color_system=None),
                      err_console=Console(file=out, width=200, color_system=None))
    runtime.out = out
    return runtime


def fill(rt, line):
    args = rt.parser.parse_args(line.split())
    fill_context(args, rt.context)
    return args


def parse_error(rt, line):
    with pytest.raises(UsageError) as e:
        rt.parser.parse_args(line.split())
    return str(e.value)


# --- abbreviations -------------------------------------------------------------------------

def _parsers(parser):
    yield parser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for sub in action.choices.values():
                yield from _parsers(sub)


def test_every_parser_of_the_program_refuses_abbreviations(rt):
    found = list(_parsers(rt.parser))
    assert len(found) > 60                                   # the whole tree, not a branch
    assert [p.prog for p in found if p.allow_abbrev] == []


def test_a_shortened_flag_is_refused_wherever_it_is_typed(rt):
    for line in ('data stats --las 100', 'case organise out --no-ver --t1 5',
                 'case upload plt --remot cloud', 'run post full --fre 5', 'auto status --onl needs'):
        assert 'unrecognized arguments' in parse_error(rt, line), line


# --- displacement --------------------------------------------------------------------------

CONFLICTS = ('data stats --var dy --func rms {}', 'data table --var dy {}',
             'data check steady --var dy {}', 'plot --var dy {}')


@pytest.mark.parametrize('line', CONFLICTS)
@pytest.mark.parametrize('typed', ('--t1 5 --last 100', '--last 100 --t1 5',
                                   '--t2 9 --last 100', '--last 100 --t2 9'))
def test_two_typed_flags_that_contradict_each_other_are_refused_in_either_order(rt, line, typed):
    message = parse_error(rt, line.format(typed))
    assert 'cannot both be typed' in message and '--last' in message


def test_one_typed_flag_and_the_other_from_use_is_fine(rt):
    rt.execute_line('use last:100')
    assert fill(rt, 'data stats --var dy --func rms --t1 5').last is None
    rt.execute_line('unuse last')
    rt.execute_line('use t1:5')
    assert fill(rt, 'data stats --var dy --func rms --last 100').last == 100   # cuts that window


def test_a_typed_range_displaces_use_last_and_says_so(rt):
    rt.execute_line('use last:1000')
    rt.out.truncate(0)
    args = fill(rt, 'data stats --var dy --func rms --t1 5')
    assert args.t1 == 5 and args.last is None
    assert 'last: 1000 (use) ignored: --t1 typed' in rt.out.getvalue()


def test_use_last_alone_is_still_used_and_not_called_ignored(rt):
    rt.execute_line('use last:1000')
    rt.out.truncate(0)
    args = fill(rt, 'data stats --var dy --func rms')
    assert args.last == 1000 and 'ignored' not in rt.out.getvalue()


def test_a_typed_end_displaces_use_time_for_both_ends(rt):
    rt.execute_line('use time:50')
    rt.out.truncate(0)
    args = fill(rt, 'data stats --var dy --func rms --t2 90')
    assert (args.t1, args.t2) == (None, 90)                  # time fills no end
    assert 'time: 50.0 (use) ignored: --t2 typed' in rt.out.getvalue()


def test_use_time_alone_still_fills_both_ends(rt):
    rt.execute_line('use time:50')
    args = fill(rt, 'data stats --var dy --func rms')
    assert (args.t1, args.t2) == (50, 50)


def test_use_t1_stays_when_only_t2_is_typed(rt):
    rt.execute_line('use t1:10')
    args = fill(rt, 'data stats --var dy --func rms --t2 90')
    assert (args.t1, args.t2) == (10, 90)
