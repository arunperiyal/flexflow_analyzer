"""Tests for the mode words of run main (restart/reset) and run post (full/convert)."""

import argparse

import pytest

from src.commands.run import RunCommand
from src.commands.run.main_impl import command as main_cmd
from src.commands.run.post_impl import command as post_cmd


@pytest.fixture
def parse():
    parser = argparse.ArgumentParser()
    RunCommand().setup_parser(parser.add_subparsers(dest='command'))

    def run(*words):
        return parser.parse_args(['run', *words])

    return run


def test_main_restart_takes_tsid_then_case(parse):
    args = parse('main', 'restart', '5000', 'Case001', '--dry-run')
    assert main_cmd._take_main_mode(args)
    assert (args.restart, args.reset, args.case) == (5000, False, 'Case001')


def test_main_restart_without_case_leaves_it_to_context(parse):
    args = parse('main', 'restart', '5000')
    assert main_cmd._take_main_mode(args)
    assert (args.restart, args.case) == (5000, None)


def test_main_reset_and_plain_case(parse):
    args = parse('main', 'reset', 'Case001')
    assert main_cmd._take_main_mode(args)
    assert (args.restart, args.reset, args.case) == (None, True, 'Case001')

    args = parse('main', 'Case001')
    assert main_cmd._take_main_mode(args)
    assert (args.restart, args.reset, args.case) == (None, False, 'Case001')


@pytest.mark.parametrize('words, message', [
    (('restart',), 'needs a timestep'),
    (('restart', 'Case001'), 'must be an integer'),
    (('restart', '0'), 'positive'),
    (('restart', '5000', 'Case001', 'extra'), "unexpected argument 'extra'"),
    (('Case001', 'extra'), "unexpected argument 'extra'"),
])
def test_main_mode_errors(parse, capsys, words, message):
    assert not main_cmd._take_main_mode(parse('main', *words))
    assert message in capsys.readouterr().out


def test_post_full_and_convert(parse):
    args = parse('post', 'full', 'Case001', '--upto', '5000')
    assert post_cmd._take_post_mode(args)
    assert (args.post_mode, args.convert, args.case, args.upto) == ('full', False, 'Case001', 5000)

    args = parse('post', 'convert')
    assert post_cmd._take_post_mode(args)
    assert (args.post_mode, args.convert, args.case) == ('convert', True, None)


def test_post_needs_a_mode_to_submit(parse, capsys):
    assert not post_cmd._take_post_mode(parse('post', 'Case001'))
    assert 'needs a mode' in capsys.readouterr().out


def test_post_cleanup_only_and_show_need_no_mode(parse):
    args = parse('post', 'Case001', '--cleanup-only')
    assert post_cmd._take_post_mode(args)
    assert args.case == 'Case001'
    assert post_cmd._take_post_mode(parse('post', '--show'))


def test_post_rejects_extra_words(parse, capsys):
    assert not post_cmd._take_post_mode(parse('post', 'full', 'Case001', 'extra'))
    assert "unexpected argument 'extra'" in capsys.readouterr().out
