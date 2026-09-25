"""
FlexFlow's shell contexts: what `use case:C1 node:24 t1:50 ...` can set, and
how commands take them.

A parser asks for a context where it declares the argument:

    case_arg(show_parser)                       # positional case
    node_arg(table_parser, help='Node to read')  # --node
    time_window(organise_parser)                # --t1/--t2 from t1/t2 or time

and the value is filled in after parsing when the user left it out. There is
no table of which command takes what at which position to keep in step with
the parsers.

Code with no args to hand (helpers deep in a command) reads the shell state
through current_case() / current_dir() / current_rundir().
"""

from pathlib import Path
from typing import Optional

from shellkit import ContextKey, add_context_arg, current_runtime, explicit


# ---------------------------------------------------------------------------
# Parsing `use` values
# ---------------------------------------------------------------------------

def _parse_case(raw, rt):
    """A case directory, made absolute against the shell's cwd; `*` for every case."""
    if raw == '*':
        return '*'
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (rt.cwd if rt else Path.cwd()) / path
    path = path.resolve()
    if not path.exists():
        raise ValueError(f"case directory does not exist: {path}")
    return str(path)


def _parse_rundir(raw, rt):
    """A run directory inside the case. Without a case it is kept as typed."""
    case = rt.context.get('case') if rt else None
    if not case or case == '*':
        return raw
    path = Path(raw[2:] if raw.startswith('./') else raw)
    if not path.is_absolute():
        path = Path(case) / path
    return str(path.resolve())


def _non_negative_int(raw):
    value = int(raw)
    if value < 0:
        raise ValueError("must be non-negative")
    return value


def _positive_int(raw):
    value = int(raw)
    if value <= 0:
        raise ValueError("must be a positive integer")
    return value


def _parse_remote(raw):
    from src.utils.remote_config import RemoteConfig
    if not RemoteConfig().remote_exists(raw):
        raise ValueError(f"remote '{raw}' not found (`remote list` shows them)")
    return raw


def _complete_remotes(rt, prefix):
    try:
        from src.utils.remote_config import RemoteConfig
        return [(r['name'], f"{r.get('user')}@{r.get('ip')}")
                for r in RemoteConfig().get_all_remotes()]
    except Exception:
        return []


def _case_name(value):
    return '*' if value == '*' else Path(value).name


CONTEXTS = [
    ContextKey('case', parse=_parse_case, path=True, label='c', style='#00aaff bold',
               format=_case_name,
               description='Case directory (or * for every case in the .cases registry)'),
    ContextKey('problem', label='p', style='#ffaa00', description='Problem name'),
    ContextKey('rundir', parse=_parse_rundir, path=True, label='r', style='#ff00ff',
               format=lambda v: Path(v).name,
               description='Run directory inside the case (e.g. RUN_1)'),
    ContextKey('node', parse=_non_negative_int, label='n',
               description='Node ID for data/plot commands'),
    ContextKey('time', parse=float, clears=('t1', 't2'),
               description='A single timestep -- clears t1/t2, and they clear it'),
    ContextKey('t1', parse=float, clears=('time',),
               description='Start of a timestep range (clears time)'),
    ContextKey('t2', parse=float, clears=('time',),
               description='End of a timestep range (clears time)'),
    ContextKey('remote', parse=_parse_remote, complete=_complete_remotes, label='rem',
               style='#ffaaee', description="Remote machine for 'case upload/download'"),
    ContextKey('var', style='#00ddaa',
               description='Variable(s) for field extract, data table/stats'),
    ContextKey('zone', style='#dd88ff',
               description='Zone for field extract/compute/convert/render'),
    ContextKey('freq', parse=_positive_int, style='#ffcc00',
               description='PLT output frequency: field sweeps, run post, data stats, case check'),
]


# ---------------------------------------------------------------------------
# Arguments that fall back to a context
# ---------------------------------------------------------------------------

def case_arg(parser, dest='case', help='Case directory path', **kwargs):
    """The positional case, filled from `use case:` when omitted."""
    flags = () if dest == 'case' else (dest,)
    return add_context_arg(parser, 'case', *flags, required=False, help=help, **kwargs)


def context_flag(parser, key, *flags, **kwargs):
    """A flag filled from the `key` context when omitted."""
    return add_context_arg(parser, key, *flags, required=False, **kwargs)


def node_arg(parser, **kwargs):
    kwargs.setdefault('type', int)
    return context_flag(parser, 'node', '--node', **kwargs)


def freq_arg(parser, **kwargs):
    kwargs.setdefault('type', int)
    return context_flag(parser, 'freq', '--freq', **kwargs)


def time_window(parser, t1_flag='--t1', t2_flag='--t2', when=None,
                t1_kwargs=None, t2_kwargs=None):
    """
    A --t1/--t2 pair filled from the t1/t2 contexts, or from a single `time`
    as the window [time, time] -- but only when neither end was typed, so a
    typed --t1 is never paired with an end the user did not ask for.

    Parameters:
        t1_flag, t2_flag: The flags as this command spells them
                          (plot takes --start-time/--end-time)
        when: namespace -> bool; the contexts apply only when it is true
              (case upload/download: only with --binary)
    """
    t1_dest = t1_flag.lstrip('-').replace('-', '_')
    t2_dest = t2_flag.lstrip('-').replace('-', '_')

    def end(key, other_dest):
        def resolve(store, ns):
            if when is not None and not when(ns):
                return None
            if store.is_set(key):
                return store.get(key)
            if store.is_set('time') and not explicit(ns, other_dest):
                return store.get('time')
            return None
        return resolve

    for key, flag, other, kw in (('t1', t1_flag, t2_dest, t1_kwargs),
                                 ('t2', t2_flag, t1_dest, t2_kwargs)):
        kw = dict(kw or {})
        kw.setdefault('type', float)
        context_flag(parser, key, flag, resolve=end(key, other), **kw)


def timestep_arg(parser, from_t1=False, **kwargs):
    """
    --timestep filled from `time` (as a whole step). With from_t1, a t1
    context stands in when no time is set -- `field convert` takes one step,
    so the start of a range is the step it gets.
    """
    def resolve(store, ns):
        if store.is_set('time'):
            return int(store.get('time'))
        if from_t1 and store.is_set('t1'):
            return int(store.get('t1'))
        return None

    kwargs.setdefault('type', int)
    return context_flag(parser, 'time', '--timestep', resolve=resolve, **kwargs)


# ---------------------------------------------------------------------------
# Shell state for code without args to hand
# ---------------------------------------------------------------------------

def current_case() -> Optional[str]:
    """The `use case:` value (an absolute path, or '*'), or None."""
    rt = current_runtime()
    return rt.get('case') if rt else None


def current_rundir() -> Optional[str]:
    rt = current_runtime()
    return rt.get('rundir') if rt else None


def current_dir() -> Path:
    """The shell's working directory (the process cwd outside the shell)."""
    rt = current_runtime()
    return rt.cwd if rt else Path.cwd()
