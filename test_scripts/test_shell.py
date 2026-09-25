"""FlexFlow on shellkit: contexts, how commands take them, completion, builtins.

The generic shell (history, aliases, pipes, `use list`/`use last`, settings)
is tested in shellkit itself; these cover what FlexFlow declares on top.
"""

import io
from pathlib import Path

import pytest
from rich.console import Console

from shellkit import Runtime
from shellkit.completion import complete
from shellkit.context import fill_context


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Keep ~/.flexflow (history, settings) out of the real home directory."""
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    return tmp_path / 'home'


@pytest.fixture
def work(tmp_path, monkeypatch):
    work = tmp_path / 'work'
    (work / 'CaseA' / 'RUN_1').mkdir(parents=True)
    (work / 'CaseA' / 'simflow.config').write_text('')
    (work / 'CaseB').mkdir()
    monkeypatch.chdir(work)
    return work


@pytest.fixture
def rt(home, work, monkeypatch):
    from src.cli.app import create_app
    from src.utils import remote_config
    monkeypatch.setattr(remote_config.RemoteConfig, 'remote_exists',
                        lambda self, name: name == 'cluster')
    runtime = Runtime(create_app(),
                      console=Console(file=io.StringIO(), width=200, color_system=None),
                      err_console=Console(file=io.StringIO(), width=200, color_system=None))
    return runtime


def use(rt, line):
    assert rt.execute_line(f'use {line}') == 0, rt.err_console.file.getvalue()


def parsed(rt, line):
    """What the command would receive for `line`, after the context fills it."""
    args = rt.parser.parse_args(line.split())
    fill_context(args, rt.context)
    return args


def err(rt):
    return rt.err_console.file.getvalue()


# ---------------------------------------------------------------------------
# `use` values
# ---------------------------------------------------------------------------

def test_case_resolves_to_absolute_path(rt, work):
    use(rt, 'case:CaseA')
    assert rt.get('case') == str(work / 'CaseA')
    assert rt.context.keys['case'].display(rt.context.entry('case')) == 'CaseA'


def test_case_must_exist(rt):
    assert rt.execute_line('use case:Nope') == 1
    assert 'does not exist' in err(rt)


def test_case_wildcard(rt):
    use(rt, 'case:*')
    assert rt.get('case') == '*'


def test_rundir_is_relative_to_case(rt, work):
    use(rt, 'case:CaseA rundir:./RUN_1')
    assert rt.get('rundir') == str(work / 'CaseA' / 'RUN_1')


def test_node_and_freq_validation(rt):
    assert rt.execute_line('use node:-1') == 1
    assert rt.execute_line('use freq:0') == 1
    use(rt, 'node:24 freq:50')
    assert (rt.get('node'), rt.get('freq')) == (24, 50)


def test_time_and_range_clear_each_other(rt):
    use(rt, 't1:10 t2:20')
    use(rt, 'time:15')
    assert rt.context.tokens() == ['time:15']
    use(rt, 't1:5')
    assert rt.context.tokens() == ['t1:5']


def test_remote_must_be_configured(rt):
    assert rt.execute_line('use remote:elsewhere') == 1
    use(rt, 'remote:cluster')


# ---------------------------------------------------------------------------
# The case positional
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('line', [
    'case show', 'case run', 'case status', 'case out', 'case upload', 'case download',
    'case organise archive', 'case organise output', 'case organise plt',
    'case check run', 'case check archive', 'case check config', 'case check plt',
    'case check def', 'case check out', 'case check all',
    'data show', 'data table', 'data stats',
    'field info', 'field extract', 'field compute force', 'field render iso',
    'run check', 'run pre', 'run main', 'run post',
    'plot',
])
def test_case_filled_from_context(rt, work, line):
    use(rt, 'case:CaseA')
    assert parsed(rt, line).case == str(work / 'CaseA')


def test_template_script_case_dir(rt, work):
    use(rt, 'case:CaseA')
    assert parsed(rt, 'template script main').case_dir == str(work / 'CaseA')


def test_typed_case_wins(rt):
    use(rt, 'case:CaseA')
    assert parsed(rt, 'case show CaseB').case == 'CaseB'


def test_no_context_leaves_case_none(rt):
    assert parsed(rt, 'case show').case is None


@pytest.mark.parametrize('line', ['case domain', 'field convert'])
def test_case_not_filled_where_the_command_resolves_it(rt, line):
    # case domain shares the slot with body/field and reads the context itself;
    # field convert never took the case from the context
    use(rt, 'case:CaseA')
    assert parsed(rt, line).case is None


def test_wildcard_case_is_passed_through(rt):
    use(rt, 'case:*')
    assert parsed(rt, 'case out').case == '*'


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------

def test_field_extract_takes_everything(rt):
    use(rt, 'zone:FIELD var:U,V t1:100 t2:200 freq:50')
    a = parsed(rt, 'field extract')
    assert (a.zone, a.variables, a.t1, a.t2, a.freq) == ('FIELD', 'U,V', 100.0, 200.0, 50)
    assert a.timestep is None


def test_field_time_becomes_whole_timestep(rt):
    use(rt, 'time:4800')
    for sub in ('extract', 'compute force', 'render iso', 'convert'):
        a = parsed(rt, f'field {sub}')
        assert a.timestep == 4800 and getattr(a, 't1', None) is None, sub


def test_field_info_takes_no_zone(rt):
    use(rt, 'zone:FIELD')
    assert parsed(rt, 'field info').zones is False


def test_field_convert_takes_t1_as_its_step(rt):
    use(rt, 't1:300 zone:cyl')
    a = parsed(rt, 'field convert')
    assert (a.timestep, a.zone) == (300, 'cyl')


def test_typed_flag_wins(rt):
    use(rt, 'zone:FIELD')
    assert parsed(rt, 'field extract --zone cyl').zone == 'cyl'


def test_data_table_and_stats(rt):
    use(rt, 'node:24 var:U t1:5 t2:9 freq:10')
    t = parsed(rt, 'data table')
    assert (t.node, t.var, t.t1, t.t2) == (24, ['U'], 5.0, 9.0)
    assert parsed(rt, 'data stats').freq == 10
    assert parsed(rt, 'data table --var P --var Q').var == ['P', 'Q']


def test_data_show_takes_no_node(rt):
    use(rt, 'node:24')
    assert not hasattr(parsed(rt, 'data show'), 'node')


def test_single_time_is_a_window(rt):
    use(rt, 'time:7')
    for line, (d1, d2) in {
        'data table': ('t1', 't2'),
        'case organise archive': ('t1', 't2'),
        'case check plt': ('t1', 't2'),
        'plot': ('start_time', 'end_time'),
    }.items():
        a = parsed(rt, line)
        assert (getattr(a, d1), getattr(a, d2)) == (7.0, 7.0), line


def test_single_time_not_used_when_one_end_is_typed(rt):
    use(rt, 'time:7')
    a = parsed(rt, 'data table --t2 9')
    assert (a.t1, a.t2) == (None, 9.0)


def test_range_ends_fill_independently(rt):
    use(rt, 't1:3')
    a = parsed(rt, 'data table --t2 9')
    assert (a.t1, a.t2) == (3.0, 9.0)


def test_case_check_freq(rt):
    use(rt, 'freq:25 t1:1')
    assert parsed(rt, 'case check plt').freq == 25
    assert parsed(rt, 'case check all').freq == 25
    assert parsed(rt, 'case check out').t1 is None


def test_run_post_freq(rt):
    use(rt, 'freq:5')
    assert parsed(rt, 'run post').freq == 5


def test_plot_node(rt):
    use(rt, 'node:3')
    assert parsed(rt, 'plot').node == 3


def test_transfer_times_only_with_binary(rt):
    use(rt, 't1:10 remote:cluster')
    up = parsed(rt, 'case upload')
    assert (up.t1, up.to) == (None, 'cluster')
    assert parsed(rt, 'case upload --binary').t1 == 10.0
    down = parsed(rt, 'case download --binary')
    assert (down.t1, down.from_remote) == (10.0, 'cluster')


def test_echo_names_what_was_used(rt):
    use(rt, 'case:CaseA node:2')
    rt.console.file.truncate(0)
    rt.execute_line('data table --help')
    out = rt.console.file.getvalue()
    assert 'Using case: CaseA' in out and 'Using node: 2' in out


# ---------------------------------------------------------------------------
# Shell state for helpers
# ---------------------------------------------------------------------------

def test_current_helpers(rt, work):
    from src.cli.context import current_case, current_dir, current_rundir
    use(rt, 'case:CaseA rundir:RUN_1')
    assert current_case() == str(work / 'CaseA')
    assert current_rundir() == str(work / 'CaseA' / 'RUN_1')
    rt.execute_line('cd CaseB')
    assert current_dir() == work / 'CaseB'


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------

def texts(rt, line):
    return [c.text for c in complete(rt, line)]


def test_completion_of_commands_and_subcommands(rt):
    assert 'case' in texts(rt, 'ca')
    assert {'show', 'create', 'organise', 'check', 'upload'} <= set(texts(rt, 'case '))
    assert texts(rt, 'case organise ') == ['archive', 'output', 'plt']


def test_completion_of_flags(rt):
    got = texts(rt, 'case upload --')
    assert {'--to', '--binary', '--t1', '--resume'} <= set(got)


def test_described_positionals(rt):
    cands = complete(rt, 'field render ')
    assert [c.text for c in cands] == ['iso', 'slice', 'colorbar']
    assert cands[0].meta == 'Isosurface of a scalar'
    assert texts(rt, 'field compute force_') == ['force_coeff']
    assert texts(rt, 'case domain ') == ['body', 'field']
    assert texts(rt, 'def time ') == ['maxTime', 'inc']


def test_file_flags_filter_extensions(rt, work):
    (work / 'view.yml').write_text('')
    (work / 'data.plt').write_text('')
    assert texts(rt, 'field render iso --config ') == ['CaseA/', 'CaseB/', 'view.yml']


def test_case_positional_completes_directories(rt):
    assert texts(rt, 'case show Ca') == ['CaseA/', 'CaseB/']


def test_remote_completion(rt, monkeypatch):
    from src.utils import remote_config
    monkeypatch.setattr(remote_config.RemoteConfig, 'get_all_remotes',
                        lambda self: [{'name': 'cluster', 'user': 'me', 'ip': '1.2.3.4'}])
    assert texts(rt, 'case upload --to ') == ['cluster']
    assert texts(rt, 'use remote:') == ['remote:cluster']


# ---------------------------------------------------------------------------
# Builtins
# ---------------------------------------------------------------------------

def test_file_style():
    from src.cli.builtins import file_style
    assert file_style(Path('run.sh')) == 'yellow'
    assert file_style(Path('slurm-123.out')) == 'yellow'
    assert file_style(Path('riser.othd')) == 'magenta'
    assert file_style(Path('notes.txt')) is None


def test_find_lists_cases(rt):
    rt.console.file.truncate(0)
    assert rt.execute_line('find') == 0
    out = rt.console.file.getvalue()
    assert 'CaseA' in out and 'CaseB' not in out


def test_web_usage_and_stop_when_not_running(rt):
    rt.execute_line('web')
    assert 'Usage' in rt.console.file.getvalue()
    rt.execute_line('web stop')
    assert 'not running' in err(rt)
    assert rt.execute_line('web restart') == 2


def test_web_start_rejects_missing_root(rt):
    assert rt.execute_line('web start --root nowhere') == 1
    assert 'Not a directory' in err(rt)


def test_help_lists_flexflow_pieces(rt):
    rt.execute_line('help')
    out = rt.console.file.getvalue()
    for word in ('case', 'field', 'web', 'quota', 'use case:Case015'):
        assert word in out


def test_oneshot_from_main(home, work, capsys):
    import main
    import sys
    argv = sys.argv
    sys.argv = ['ff', 'template', 'script', '--help']
    try:
        assert main.main() in (0, None)
    finally:
        sys.argv = argv
    assert 'script' in capsys.readouterr().out.lower()
