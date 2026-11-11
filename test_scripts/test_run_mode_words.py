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


def test_main_restart_with_time_and_case(parse):
    args = parse('main', 'restart', 'Case001', '--time', '5000', '--dry-run')
    assert main_cmd._take_main_mode(args)
    assert (args.restart, args.restart_last, args.reset, args.case) == (5000, False, False, 'Case001')


def test_main_restart_without_time_is_from_the_last_written_file(parse):
    args = parse('main', 'restart', 'Case001')
    assert main_cmd._take_main_mode(args)
    assert (args.restart, args.restart_last, args.case) == (None, True, 'Case001')
    args = parse('main', 'restart')
    assert main_cmd._take_main_mode(args)
    assert (args.restart_last, args.case) == (True, None)


def test_main_reset_and_plain_case(parse):
    args = parse('main', 'reset', 'Case001')
    assert main_cmd._take_main_mode(args)
    assert (args.restart, args.reset, args.case) == (None, True, 'Case001')

    args = parse('main', 'Case001')
    assert main_cmd._take_main_mode(args)
    assert (args.restart, args.restart_last, args.reset, args.case) == (None, False, False, 'Case001')


@pytest.mark.parametrize('words, message', [
    (('restart', '5000', 'Case001'), "no longer accepted"),
    (('restart', '5000'), "run main restart [case] --time 5000"),
    (('restart', 'Case001', '--time', 'abc'), "--time must be an integer"),
    (('restart', 'Case001', '--time', '0'), "positive"),
    (('restart', 'Case001', 'extra'), "unexpected argument 'extra'"),
    (('Case001', 'extra'), "unexpected argument 'extra'"),
    (('Case001', '--time', '5000'), "--time belongs to restart"),
    (('reset', 'Case001', '--time', '5000'), "--time belongs to restart"),
])
def test_main_mode_errors(parse, capsys, words, message):
    assert not main_cmd._take_main_mode(parse('main', *words))
    assert message in capsys.readouterr().out


def _case_with_config(tmp_path, text):
    (tmp_path / 'simflow.config').write_text(text)
    return tmp_path


def _console():
    from rich.console import Console
    return Console(file=open('/dev/null', 'w'))


def test_restart_with_time_sets_the_step_and_the_flag(tmp_path):
    case = _case_with_config(tmp_path, '#restartTsId = 100\nrestartFlag = 0\nnsg = 4\n')
    assert main_cmd.handle_restart(case, 8150, _console())
    text = (case / 'simflow.config').read_text()
    assert 'restartTsId = 8150' in text and 'restartFlag = 1' in text


def test_restart_without_time_comments_out_the_step_and_sets_the_flag(tmp_path):
    case = _case_with_config(tmp_path, 'restartTsId = 5740\nrestartFlag = 0\nnsg = 4\n')
    assert main_cmd.handle_restart_last(case, _console())
    lines = (case / 'simflow.config').read_text().splitlines()
    assert '#restartTsId = 5740' in lines and 'restartFlag = 1' in lines and 'nsg = 4' in lines


def test_the_restart_asks_and_a_no_changes_nothing(tmp_path, monkeypatch):
    args = argparse.Namespace(restart=None, restart_last=True, yes=False)
    monkeypatch.setattr('builtins.input', lambda *a: 'n')
    assert not main_cmd.confirm_restart(tmp_path, args, _console())
    monkeypatch.setattr('builtins.input', lambda *a: 'y')
    assert main_cmd.confirm_restart(tmp_path, args, _console())


def test_yes_skips_the_question(tmp_path, monkeypatch):
    args = argparse.Namespace(restart=5000, restart_last=False, yes=True)
    monkeypatch.setattr('builtins.input', lambda *a: (_ for _ in ()).throw(AssertionError('asked')))
    assert main_cmd.confirm_restart(tmp_path, args, _console())


def test_no_answer_at_all_is_a_no(tmp_path, monkeypatch):
    args = argparse.Namespace(restart=5000, restart_last=False, yes=False)

    def eof(*a):
        raise EOFError
    monkeypatch.setattr('builtins.input', eof)
    assert not main_cmd.confirm_restart(tmp_path, args, _console())


def test_post_full_and_convert(parse):
    args = parse('post', 'full', 'Case001', '--t2', '5000')
    assert post_cmd._take_post_mode(args)
    assert (args.post_mode, args.convert, args.case, args.t2) == ('full', False, 'Case001', 5000)

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
