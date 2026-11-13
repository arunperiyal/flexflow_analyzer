# Instructions for Copilot

FlexFlow Manager: a command-line shell (`ff`) and a Flask web UI for creating,
running and analysing FlexFlow riser simulations on an HPC cluster. Python,
built on the `shellkit` shell framework.

## Read first

- `docs/development/PLAN.md`: the plan, as phases split into tasks. Work only
  on the phase you were given.
- `.claude/context/code-map.md`: where code is and how a command is laid out.
- `.claude/rules/git-workflow.md` and `.claude/rules/output.md`: the rules
  below, in full.

## Phases you may take

These do not touch the `auto` code, which is being changed in another session:

- **Phase 9** (`flowreel-export`): files for FlowReel, in the `field` command.
- **Phase 10** (`docs-install`): the installer and two pages in
  `docs/development/`. Skip its last task (`NEXT_SESSION.md`).
- **Phase 11** (`webapp-checklist`): `docs/architecture/webapp.md` §11 and §12.

Do not start Phases 6, 7, 8, 16 or 17, and do not edit `src/core/auto/`,
`src/commands/auto/`, `src/core/transfer/`, `src/core/chain.py` or
`src/commands/case/organise_impl/`.

## Rules

- One branch per phase, cut from `main`, named as the plan says.
- One commit per task. Tick the task in `docs/development/PLAN.md` in the
  same commit.
- Commit messages are plain: what changed, in the style of `git log`. No
  mention of an AI tool and no `Co-Authored-By` trailer.
- Never stage `prompt.md`. Do not push or merge unless asked.
- Run `python3 -m pytest test_scripts -q` before each commit (about two
  minutes; every test passes on `main`).
- A user-visible change gets an entry under `## Unreleased` in `CHANGELOG.md`.
- Documents for people go in `docs/`, in the folder that matches their
  purpose, with a row in `docs/README.md`.
- `docs/architecture/auto.md` and `webapp.md` are cited from the code by
  section number: add sections at the end, never renumber.
- Data safety comes first: nothing is deleted without a verified copy.

## When a phase is done

Move it to the Done table of the plan as one line, and say what was left out
or could not be checked.
