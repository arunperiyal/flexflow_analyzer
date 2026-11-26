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


# --- the other `case` commands (Phase 39) ------------------------------------------------

OLD_FORMS = ('case show CS1', 'case run CS1', 'case out CS1', 'case check run CS1',
             'case check history CS1', 'case check config CS1', 'case check plt CS1',
             'case check def CS1', 'case check out CS1', 'case check data CS1',
             'case check all CS1', 'case upload CS1', 'case download CS1',
             'case upload plt CS1', 'case status CS1', 'case domain CS1', 'case domain body CS1')


@pytest.mark.parametrize('line', OLD_FORMS)
def test_the_case_as_a_word_is_refused_and_says_what_to_type(shell, capsys, line):
    status, text = shell(line)
    seen = capsys.readouterr()
    err = text + seen.out + seen.err
    assert status != 0 and '--case' in err, line


def test_a_typed_case_flag_is_taken_by_every_case_command(shell):
    import argparse
    from src.commands.case import CaseCommand
    parser = argparse.ArgumentParser()
    CaseCommand().setup_parser(parser.add_subparsers(dest='command'))
    for line in ('show', 'run', 'out', 'check run', 'check history', 'check config',
                 'check plt', 'check def', 'check out', 'check data', 'check all', 'upload plt',
                 'download rst', 'status', 'domain body', 'organise history update'):
        got = parser.parse_args(['case', *line.split(), '--case', 'CS1'])
        assert got.case == 'CS1', line


# --- data, plot, field (Phase 40) ---------------------------------------------------------

OTHER_OLD_FORMS = ('data show CS1', 'data table CS1', 'data stats CS1', 'data check steady CS1',
                   'plot CS1', 'field info CS1', 'field extract CS1', 'field convert CS1',
                   'field compute force CS1', 'field render iso CS1')


@pytest.mark.parametrize('line', OTHER_OLD_FORMS)
def test_data_plot_field_refuse_the_case_as_a_word(shell, capsys, line):
    status, text = shell(line)
    seen = capsys.readouterr()
    err = text + seen.out + seen.err
    assert status != 0 and '--case CS1' in err, line


def test_data_plot_field_take_the_case_flag(shell):
    import argparse
    from src.cli.app import create_app
    parser = create_app().build_parser()
    for line in ('data show', 'data table', 'data stats', 'data check steady', 'plot',
                 'field info', 'field extract', 'field convert', 'field compute force',
                 'field render iso'):
        got = parser.parse_args([*line.split(), '--case', 'CS1'])
        assert got.case == 'CS1', line


# --- names, values and files are flags (Phase 41) -----------------------------------------

VALUE_FORMS = (('case create CS9', '--name CS9'), ('remote add srv', '--name srv'),
               ('remote modify srv', '--name srv'), ('remote delete srv', '--name srv'),
               ('remote set-path srv', '--name srv'), ('check f.othd', '--file f.othd'),
               ('field check a.vtu', '--file a.vtu'),
               ('template plot single out.yml', '--output out.yml'),
               ('template case multi out.yml', '--output out.yml'),
               ('def var DIA 2', '--name DIA'), ('def time maxTime 5000', '--value 5000'),
               ('def freq out 50', '--value 50'))


@pytest.mark.parametrize('line, flag', VALUE_FORMS)
def test_a_value_typed_as_a_word_is_refused_and_the_flag_is_named(shell, capsys, line, flag):
    status, text = shell(line)
    seen = capsys.readouterr()
    assert status != 0 and flag in text + seen.out + seen.err, line


def test_the_flags_take_the_values(shell):
    from src.cli.app import create_app
    parser = create_app().build_parser()
    got = parser.parse_args('case create --name CS9'.split())
    assert got.case_name == 'CS9'
    for verb in ('add', 'modify', 'delete', 'set-path'):
        assert parser.parse_args(['remote', verb, '--name', 'srv']).name == 'srv'
    assert parser.parse_args('check --file f.othd'.split()).file == 'f.othd'
    assert parser.parse_args('field check --file a.vtu'.split()).file == 'a.vtu'
    assert parser.parse_args('template plot single --output o.yml'.split()).output == 'o.yml'
    got = parser.parse_args('def var --name DIA --value 2'.split())
    assert (got.name, got.value) == ('DIA', '2')
    got = parser.parse_args('def time maxTime --value 5000'.split())
    assert (got.kind, got.value) == ('maxTime', '5000')
    assert parser.parse_args('def freq out --value 50 --case CS1'.split()).case == 'CS1'
    assert parser.parse_args('template script main --case CS1'.split()).case_dir == 'CS1'


# --- run (Phase 43) -----------------------------------------------------------------------

RUN_OLD_FORMS = (('run check CS1', '--case CS1'), ('run check mesh CS1', '--case CS1'),
                 ('run pre CS1', '--case CS1'), ('run main CS1', '--case CS1'),
                 ('run main restart CS1', '--case CS1'), ('run main restart 5000', '--case 5000'),
                 ('run post full CS1', '--case CS1'), ('run list log CS1', '--case CS1'),
                 ('run sq 1258586', '--job 1258586'), ('run sc 1258586', '--job 1258586'),
                 ('run sb post.sh', '--script post.sh'))


@pytest.mark.parametrize('line, flag', RUN_OLD_FORMS)
def test_run_refuses_a_case_job_or_script_typed_as_a_word(shell, capsys, line, flag):
    status, text = shell(line)
    seen = capsys.readouterr()
    assert flag in text + seen.out + seen.err, line


def test_run_takes_its_flags():
    from src.cli.app import create_app
    parser = create_app().build_parser()
    for line in ('check', 'check mesh', 'pre', 'main', 'main restart', 'main reset', 'post full',
                 'post convert', 'list log'):
        assert parser.parse_args(['run', *line.split(), '--case', 'CS1']).case == 'CS1', line
    got = parser.parse_args('run sq watch --interval 5'.split())
    assert (got.target, got.interval) == ('watch', 5.0)
    assert parser.parse_args('run sq find --key CS4'.split()).key == 'CS4'
    assert parser.parse_args('run sq --job 123 --out'.split()).job == '123'
    assert parser.parse_args('run sc --name postCS1'.split()).name == 'postCS1'
    got = parser.parse_args(['run', 'sb', '--script', 'post.sh', '--sbatch-args=--dependency=afterok:1'])
    assert (got.script, got.sbatch_args) == ('post.sh', '--dependency=afterok:1')
