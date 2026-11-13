# Code map

Where things are in the code. Read this before looking for a file.

## Entry points

| File | What it is |
|---|---|
| `main.py` | Entry point. `ff` starts the shell, `ff <command>` runs one command, `--ui` starts the web UI |
| `src/cli/app.py` | Declares the app on shellkit: banner, settings, and `_register_commands()`, the list of every command |
| `__version__.py` | The version |
| `install.sh`, `install/` | Shell installer (conda environment, alias) |
| `flexflow.spec` | PyInstaller build |

The shell itself (prompt, history, `use`, pipes, completion) is the external
package `shellkit`, pinned in `requirements.txt`. FlexFlow only declares
commands, contexts and builtins.

## `src/`

| Folder | Holds |
|---|---|
| `cli/` | App declaration (`app.py`), shell contexts such as `case:` `node:` `t1:` (`context.py`), own builtins `web`, `quota`, `missing` (`builtins.py`), tab completion (`completers.py`), generated bash/zsh/fish completion (`completion.py`) |
| `commands/` | One package per command. Parsing and help only; the logic is in `*_impl/` and `core/` |
| `core/` | What a case is and how its files are read: no command-line code |
| `core/auto/` | The `auto` workflow, in the order it runs: `observe` (read-only snapshot) → `decide` (pure rules) → `executor` (acts), with `ledger`, `runlog`, `report`, `cloud`, `conf`, `stretches` |
| `core/readers/` | OTHD and OISD time-history readers; `series.py` reads them as named variables |
| `core/parsers/` | `.def` parser |
| `plt/` | Binary PLT without Tecplot: `fxplt.py` reader, `convert.py` to VTU, `render.py` PNGs via pyvista, `derive.py`, `surface.py`, `camera.py` |
| `utils/` | Colours, logger, progress bars, SSH client, remote config (`~/.flexflow/remotes.json`), CPU cap, plot helpers |
| `web/` | Flask web UI: `server.py` (app factory), `api/` (one blueprint per area), `services/` (logic behind the API), `static/js`, `static/css`, `templates/index.html`, vendored MathJax and vtk.js under `static/vendor/` |
| `templates/` | Example YAML configs and the SLURM job scripts (`scripts/`) that `case create` and `template` copy |
| `installer/` | `--install`: copies files, converts `docs/**/*.md` to HTML |

## How a command is laid out

```
src/commands/<group>/
  __init__.py            the Command class: setup_parser() builds every
                         subparser, execute() dispatches to an _impl
  <sub>_impl/
    __init__.py
    command.py           what the subcommand does
    help_messages.py     its --help and --examples text
```

- Commands subclass `BaseCommand` (`src/commands/base.py`, which is shellkit's).
- Groups: `case`, `data`, `field`, `run`, `auto`, `remote`, `template`,
  `visualization` (`plot`, `compare`), `utils` (`docs`); `check.py`
  and `def_cmd.py` are single-file commands with `check_impl/`, `def_impl/`.
- `auto` is flat: `init.py`, `show.py`, `apply.py`, with the logic in
  `src/core/auto/`.
- A new command is registered in `_register_commands()` in `src/cli/app.py`
  and added to the completion lists in `src/cli/completion.py`.
- `src/commands/case_iteration.py` handles `case:*` (run over every case).
- Help text is hand-written in `help_messages.py`, not argparse's: when a
  flag changes, change the parser, the help text and the completion.

## Core modules worth knowing

| File | Holds |
|---|---|
| `core/case.py` | The case manager: a case directory and what is in it |
| `core/cases_file.py` | `.cases.yml`, one per folder of cases (registry, remotes, `auto:` settings) |
| `core/case_status.py` | `.casestatus.md`, the case's own notes and log |
| `core/simflow_config.py`, `core/def_config.py` | Parsers for `simflow.config` and `.def` |
| `core/domain.py` | `domain.yml` |
| `core/history.py`, `core/restarts.py` | Where OTHD/OISD history is kept (archive, cleaned, compiled) and the `.restarts` record |
| `core/slurm.py`, `core/hpc_partition.py` | Reading the SLURM queue; partitions and directives |
| `core/plt_valid.py`, `core/settled.py` | Is a PLT whole; which `.out` steps are finished |

## Outside `src/`

| Path | Holds |
|---|---|
| `test_scripts/` | The pytest suite, `test_<command>_<topic>.py`. Run `python3 -m pytest test_scripts -q` |
| `tools/make_dummy.py`, `tools/fake_slurm.py` | Build `dummy/` (fake cases, fake SLURM, fake cloud) to try `auto` without a cluster |
| `tools/hpc_probe.sh`, `tools/nas/` | Cluster probe script; POSIX `sh` helpers for the NAS |
| `examples/standard/` | The one tracked reference case. Everything else in `examples/` is local data, ignored by git, and some tests need `examples/BR0SG0U1P0` |
| `docs/` | Documentation; `docs/README.md` is the index |

## Not in use

- `src/commands/config/`: a `config` command (`config template`) that is not
  registered in `src/cli/app.py`. Whether to remove or register it is open
  (see the backlog in `docs/development/PLAN.md`). Do not build on it.
