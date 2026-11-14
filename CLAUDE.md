# CLAUDE.md

FlexFlow Manager: a command-line shell (`ff`) and a Flask web UI for creating,
running and analysing FlexFlow riser simulations on an HPC cluster. Python,
built on the `shellkit` shell framework.

## Commands

```bash
python3 main.py                 # the interactive shell
python3 main.py case show C1    # one command
python3 main.py --ui            # the web UI
python3 -m pytest test_scripts -q
```

## Rules

Loaded from `.claude/rules/`:

- `git-workflow.md`: plan first; the user makes branches, merges, pushes and
  PRs, Claude commits one task at a time and resolves conflicts; the user
  tests and reports in `bug-report.md`; plain commit messages.
- `output.md`: no Claude Artifacts; where documents go.

## Where to look

| For | Read |
|---|---|
| Where code is and how a command is laid out | `.claude/context/code-map.md` |
| The plan: phases and tasks | `docs/development/PLAN.md` |
| Documentation index | `docs/README.md` |
| Design of `auto` and the web UI | `docs/architecture/auto.md`, `docs/architecture/webapp.md` |
| Bugs the user found testing (untracked) | `bug-report.md` |
| Notes handed over from the last session | `.claude/context/NEXT_SESSION.md` |
