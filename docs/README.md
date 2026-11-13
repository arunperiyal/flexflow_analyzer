# FlexFlow documentation

Where each document is. `flexflow docs <topic>` opens the ones marked with a
topic name.

## Installation

| Document | Topic | What it covers |
|---|---|---|
| [installation/INSTALL.md](installation/INSTALL.md) | `install` | Installing, updating and removing FlexFlow |
| [../install/README.md](../install/README.md) | | The install scripts themselves |

## Usage

| Document | Topic | What it covers |
|---|---|---|
| [usage/USAGE.md](usage/USAGE.md) | `main` | The full guide to the shell and its commands |
| [usage/REFERENCE.md](usage/REFERENCE.md) | `reference` | One-page command list |
| [usage/run.md](usage/run.md) | `run` | `run pre`, `main`, `post` and the SLURM helpers |
| [usage/case-create.md](usage/case-create.md) | `create` | `case create`: time parameters and global defaults |
| [usage/case-organise.md](usage/case-organise.md) | `organise` | `case organise`, step by step |
| [../examples/standard/README.md](../examples/standard/README.md) | | The standard reference case |
| [../tools/nas/README.md](../tools/nas/README.md) | | Shell helpers for case data on the NAS |

## Architecture

Design documents. The code cites `auto.md` and `webapp.md` by section number
(for example "docs/architecture/auto.md §13"), so their section numbers must
stay as they are.

| Document | Topic | What it covers |
|---|---|---|
| [architecture/case-structure.md](architecture/case-structure.md) | `structure` | Layout of a case directory |
| [architecture/auto.md](architecture/auto.md) | `auto` | The `auto` command: rules, checks and decisions |
| [architecture/auto_flow.html](architecture/auto_flow.html) | | Flowchart of the `auto` workflow (open in a browser) |
| [architecture/webapp.md](architecture/webapp.md) | `webapp` | The web UI: layout, node picker, HTTP API |
| [architecture/flowreel.md](architecture/flowreel.md) | | Files FlowReel expects from FlexFlow (not built yet) |

## Development

| Document | What it covers |
|---|---|
| [../CHANGELOG.md](../CHANGELOG.md) | What changed, newest first |

## Adding a document

Put it in the folder that matches its purpose, add a row here, and if it
should open with `flexflow docs`, add it to `TOPICS` in
`src/commands/utils/docs_impl/command.py`, to the help text beside it and to
the topic lists in `src/cli/completion.py`.
