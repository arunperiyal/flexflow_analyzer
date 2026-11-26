# How commands are shaped

Decided with the user on 2026-11-26. Every command follows these; a command
that does not yet is listed at the end and fixed by its own phase.

## Words and values

1. After `case` (or any command) there are **at most 3 levels**, each a word:
   subcommand, target, action. `case organise history update`,
   `case organise plt binary`.
2. A **value is always a flag, never a positional**. The case is
   `--case NAME` (`*` for every case) or comes from `use case:`. A name is
   `--name NAME` (`case create --name`, `remote add --name`); an output is
   `--output FILE`. A word never takes a case or a path.
3. **Words come before flags**, so Tab right after a word offers the next word.
4. **Flags are typed in full.** No abbreviations: parsers set
   `allow_abbrev=False`. A shortened flag is refused.

## Context (`use`)

5. A flag left out is filled from the `use` list. A flag typed **overrides**
   `use`.
6. A flag may **displace** other flags: typing `--t1` or `--t2` makes the `use`
   values of `last` and `time` ignored; typing `--time` displaces `t1`/`t2`.
   Displacement is declared once, next to the flag, per parser (so it follows
   the subcommand), and the line says what was ignored
   (`last: 1000 (use) ignored: --t1 typed`). Typing **two flags that displace
   each other** is refused with a message naming both.
7. A row passed by `|` is context for one run. A flag typed on that command
   still wins.

## Safety

8. A command that changes or deletes files prints the values it will use,
   **each tagged typed or from `use`** (`Using t1: 9850 (use)`), before it asks.
9. Deleting commands list what they will do and **ask first**. `--dry-run`
   stops after the list; `--yes` skips the question. Over several cases (`*`)
   it asks **once per case**.
10. A flag that waives a check (`--no-verify`) is never read from `use`,
    `.cases.yml` or `auto`, and `auto` never passes it.
11. A **removed form is refused** with a message that names the new form
    (`history CS1` says "use --case CS1"); it is never reinterpreted, and no
    alias is kept.

## Tests and plan

12. Every command with words has a completion test for each position, and one
    test walks all commands so a new one without it fails.
13. A new or changed form goes into `docs/development/PLAN.md` first.

## Not yet following these

Everything except `case organise` (Phase 37). The rest is Phase 38.
