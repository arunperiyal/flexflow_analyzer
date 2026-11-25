"""
Tab-completion helpers for FlexFlow's parsers.

Subcommands, flags and `choices` complete on their own (shellkit reads them
from argparse); these cover what argparse cannot say: descriptions for a
positional's values, and which kinds of file a flag takes.
"""

from shellkit import paths
from shellkit.completion import context_values


def described(*options):
    """Completer offering fixed values with a description each: ('iso', 'Isosurface')."""
    options = list(options)

    def complete(rt, prefix):
        return options
    return complete


def file_flags(parser, flags):
    """
    Complete paths after each flag (or positional dest), narrowed to the given
    extensions; an empty tuple offers every file.

    The point of the filter is the directory a case is worked in: it holds PLTs,
    .vtu sidecars, images and a config or two, and an unfiltered list is long
    enough that reading it costs more than typing the name.
    """
    by_dest = {a.dest: a for a in parser._actions}
    for flag, exts in flags.items():
        action = parser._option_string_actions.get(flag) or by_dest.get(flag)
        if action is None:
            raise KeyError(f"{parser.prog} has no argument {flag}")
        action.completer = paths(exts)


def words_in_case_slot(case_action, words):
    """
    Also offer the action `words` in the slot of the case positional, when a case
    is set by `use case:`. `case organise plt ascii` then takes `ascii` as the
    first word of the case slot (the command reads it as an action), so a Tab there
    must offer the words as well as the case directories.

    `words` is the completer of the actions positional (see `described`).
    """
    def complete(rt, prefix):
        offered = []
        if rt.context.is_set('case'):
            offered = list(words(rt, prefix))
        key = rt.context.keys.get(case_action.context_key)
        cases = list(context_values(rt, key, prefix)) if key is not None else []
        return offered + cases
    case_action.completer = complete
