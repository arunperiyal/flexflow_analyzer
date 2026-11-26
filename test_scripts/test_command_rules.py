"""Every command follows .claude/rules/command-design.md. One test walks the whole
parser tree, so a command added later that breaks a rule fails here."""

import argparse
import io

import pytest
from rich.console import Console
from shellkit import Runtime
from shellkit.completion import complete

from src.cli.app import create_app

# positional names that are values, never words: a value is a flag
VALUE_NAMES = {'case', 'case_dir', 'case_name', 'path', 'file', 'name', 'value', 'output',
               'script', 'job', 'remote', 'dir', 'extra', 'case_after'}


@pytest.fixture(scope='module')
def tree():
    return create_app().build_parser()


def walk(parser, path=()):
    """(path, parser) of every parser in the tree, the root first."""
    yield list(path), parser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                yield from walk(sub, (*path, name))


def positionals(parser):
    return [a for a in parser._actions
            if not a.option_strings and not isinstance(a, argparse._SubParsersAction)
            and a.dest != 'words' and a.help != argparse.SUPPRESS]


def test_the_tree_is_walked_whole(tree):
    paths = [' '.join(p) for p, _ in walk(tree)]
    assert len(paths) > 60
    for expected in ('case organise history', 'run post', 'auto', 'data check steady',
                     'field render', 'remote set-path', 'template script', 'def freq'):
        assert expected in paths


def test_no_command_has_more_than_three_levels_of_words_after_the_command(tree):
    """`case organise history update`: the command, then subcommand, target and action.
    The subcommand tree itself is at most command + 2 (case organise history)."""
    deepest = max(len(p) for p, _ in walk(tree))
    assert deepest <= 3, [' '.join(p) for p, _ in walk(tree) if len(p) > 3]


def test_every_positional_is_a_word_with_choices_or_a_completer(tree):
    """A word is a choice (an action, a mode, a target); a value is a flag."""
    bad = [(' '.join(p), a.dest) for p, parser in walk(tree) for a in positionals(parser)
           if not (a.choices or getattr(a, 'completer', None))]
    assert bad == []


def test_no_positional_is_named_like_a_value(tree):
    bad = [(' '.join(p), a.dest) for p, parser in walk(tree) for a in positionals(parser)
           if a.dest in VALUE_NAMES]
    assert bad == []


def test_a_command_that_works_on_a_case_takes_it_as_the_case_flag(tree):
    flagged = []
    for path, parser in walk(tree):
        for a in parser._actions:
            if a.dest in ('case', 'case_dir') and a.dest not in ('words',):
                assert a.option_strings and '--case' in a.option_strings, (path, a.dest)
                assert getattr(a, 'context_key', None) == 'case', (path, a.dest)
                flagged.append(' '.join(path))
    assert len(flagged) >= 40
    assert 'case organise history' in flagged and 'run post' in flagged and 'auto' in flagged


def test_every_parser_refuses_a_stray_word_or_takes_none(tree):
    """A parser that takes the case, a name, a value or a file catches a stray word in
    `words` (BaseCommand.run refuses it and says which flag), so a value typed as a word
    is never silently taken. The parsers with no case or value flag need not."""
    for path, parser in walk(tree):
        takes_value = any(a.option_strings and a.dest in ('case', 'case_dir', 'case_name', 'name',
                                                          'file', 'output', 'value', 'job', 'script')
                          for a in parser._actions)
        # the words of `history` / `plt` (actions) are checked one by one by the command
        has_catch = any(a.dest == 'words' for a in parser._actions) or bool(positionals(parser))
        if takes_value and not any(isinstance(a, argparse._SubParsersAction)
                                   for a in parser._actions):
            assert has_catch, ' '.join(path)


@pytest.fixture
def rt(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    (tmp_path / 'CaseA').mkdir()
    monkeypatch.chdir(tmp_path)
    return Runtime(create_app(), console=Console(file=io.StringIO(), width=200, color_system=None),
                   err_console=Console(file=io.StringIO(), width=200, color_system=None))


def test_the_completer_answers_at_every_position_of_every_command(rt, tree):
    """After each command path: the next word, or the flags; never an error, never empty
    unless the command has neither."""
    for path, parser in walk(tree):
        if not path:
            continue
        line = ' '.join(path) + ' '
        got = [c.text for c in complete(rt, line)]
        has_next = any(isinstance(a, argparse._SubParsersAction) or positionals(parser)
                       for a in parser._actions)
        has_flags = any(a.option_strings for a in parser._actions)
        assert got or not (has_next or has_flags), line
        # the words come before the flags: a flag is offered only once no word is left
        for a in positionals(parser):
            if a.choices or getattr(a, 'completer', None):
                words = [c.text for c in complete(rt, line)]
                assert not words or not words[0].startswith('-') or not has_next, line
                break


def test_every_word_a_positional_offers_completes_after_its_command(rt, tree):
    for path, parser in walk(tree):
        for a in positionals(parser)[:1]:        # the first word; later ones follow it
            completer = getattr(a, 'completer', None)
            if completer is None:
                continue
            offered = [o[0] if isinstance(o, (tuple, list)) else str(o)
                       for o in completer(rt, '')]
            if not offered:                      # paths for a file value: not a word
                continue
            line = ' '.join(path) + ' '
            got = [c.text for c in complete(rt, line)]
            assert offered[0] in got, (line, offered[:3], got[:5])
