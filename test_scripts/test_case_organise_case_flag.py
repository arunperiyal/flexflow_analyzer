"""`case organise` follows .claude/rules/command-design.md: the case is `--case NAME`
or `use case:`, never a word; a typed flag overrides `use`; the values used are
printed, tagged typed or from `use`; a case with no value says what to type."""

import io

import pytest
from rich.console import Console
from shellkit import Runtime

from src.cli.app import create_app


@pytest.fixture
def shell(tmp_path, monkeypatch):
    work = tmp_path / 'work'
    for name in ('CS1', 'CS2'):
        (work / name / 'RUN_1').mkdir(parents=True)
        (work / name / 'simflow.config').write_text('problem = riser\nnp = 1\ndir = ./RUN_1\n')
    monkeypatch.chdir(work)
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    out = io.StringIO()
    rt = Runtime(create_app(), console=Console(file=out, width=200, color_system=None),
                 err_console=Console(file=out, width=200, color_system=None))

    def run(line, capsys=None):
        status = rt.execute_line(line)
        text = out.getvalue()
        out.truncate(0)
        out.seek(0)
        return status, text
    return run


def test_the_case_from_use_and_a_typed_range_are_told_apart(shell, capsys):
    shell('use case:CS1')
    status, text = shell('case organise out --dry-run --t1 100')
    text += capsys.readouterr().out
    assert status == 0, text
    assert 'Values used: case CS1 (use) · t1 100 (typed) ·' not in text   # remote is not set
    assert 'Values used: case CS1 (use) · t1 100 (typed)' in text


def test_a_typed_case_overrides_use(shell, capsys):
    shell('use case:CS1')
    status, text = shell('case organise out --case CS2 --dry-run')
    text += capsys.readouterr().out
    assert status == 0 and 'CS2' in text.split('Values used:')[1].splitlines()[0]
    assert 'Organizing Case: CS2' in text


def test_no_case_anywhere_says_what_to_type(shell, capsys):
    status, text = shell('case organise out --dry-run')
    err = text + capsys.readouterr().err
    assert status != 0 and 'no case given' in err and '--case NAME' in err and 'use case:' in err


def test_the_old_form_with_the_case_as_a_word_is_refused_for_every_subcommand(shell, capsys):
    for line in ('case organise history CS1 update', 'case organise plt CS1 binary',
                 'case organise out CS1', 'case organise rst CS1', 'case organise vtu CS1'):
        status, text = shell(line)
        err = text + capsys.readouterr().err
        assert status != 0 and '--case CS1' in err, line


def test_a_shortened_flag_is_refused(shell, capsys):
    shell('use case:CS1')
    status, text = shell('case organise out --dry --t1 5')
    assert status != 0


def test_over_every_case_each_one_is_named_in_its_values(shell, tmp_path, capsys):
    from registry_files import write_registry
    work = tmp_path / 'work'
    write_registry(work, [{"name": n, "path": str(work / n)} for n in ('CS1', 'CS2')])
    status, text = shell('case organise out --case * --dry-run')
    text += capsys.readouterr().out
    assert 'Values used: case CS1 (typed)' in text and 'Values used: case CS2 (typed)' in text
    assert text.count('Dry run:') == 2                   # each case is its own run
