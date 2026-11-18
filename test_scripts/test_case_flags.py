"""One flag vocabulary for `case` (docs/development/PLAN.md, Phase 31): every command that
deletes takes the same safety flags, spelled the same, and no option goes by two names."""

import argparse
import collections

import pytest

from src.commands.case import CaseCommand


def parsers():
    """(path, parser) for every parser under `case`."""
    root = argparse.ArgumentParser(prog='ff')
    CaseCommand().setup_parser(root.add_subparsers(dest='command'))
    out = []

    def walk(parser, path):
        out.append((path, parser))
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, sub in action.choices.items():
                    walk(sub, f"{path} {name}")
    walk(root.__dict__['_subparsers']._group_actions[0].choices['case'], 'case')
    return out


def options(parser):
    return {o for a in parser._actions for o in a.option_strings}


ALL = parsers()
ORGANISE = [(p, q) for p, q in ALL if p.startswith('case organise ') and p.count(' ') == 2]


def test_every_organise_command_takes_the_same_safety_flags():
    assert len(ORGANISE) == 5, [p for p, _ in ORGANISE]
    for path, parser in ORGANISE:
        missing = {'--dry-run', '--yes', '-y', '--log', '-v', '--verbose', '-h', '--help'} - options(parser)
        assert not missing, f"{path} lacks {sorted(missing)}"


@pytest.mark.parametrize('old', ['--no-confirm', '--examples', '--clean-vtu', '--keep-orphans'])
def test_the_old_spellings_are_gone_from_case(old):
    for path, parser in ALL:
        assert old not in options(parser), f"{path} still has {old}"


def test_no_option_has_two_names_for_one_thing():
    """Long names within one command that differ only by a hyphen or underscore."""
    for path, parser in ALL:
        seen = collections.Counter(o.lstrip('-').replace('_', '-') for o in options(parser)
                                   if o.startswith('--'))
        assert not [o for o, n in seen.items() if n > 1], path


def test_actions_are_words_not_flags():
    plt = options(dict(ALL)['case organise plt'])
    history = options(dict(ALL)['case organise history'])
    for old in ('--delete-ascii', '--delete-binary'):
        assert old not in plt
    for old in ('--update', '--clean', '--compile', '--verify', '--prune'):
        assert old not in history
    assert '--verify' not in options(dict(ALL)['case check plt'])
