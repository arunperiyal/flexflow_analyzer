# Output and documents

- **Never use Claude Artifacts** (no publishing pages to claude.ai). When a
  page, diagram or report is useful, write a standalone HTML file into the
  repository (e.g. `docs/architecture/auto_flow.html`) that opens in a local
  browser. Load any library it needs (e.g. Mermaid) from a CDN in the file
  itself.
- Documents for people go in `docs/`, in the folder that matches their
  purpose (`installation/`, `usage/`, `architecture/`, `development/`), with a
  row in `docs/README.md`. Only `README.md`, `CHANGELOG.md` and `CLAUDE.md`
  stay in the repo root.
- Files meant for Claude go in `.claude/`: rules that always apply in
  `.claude/rules/`, background to read when needed in `.claude/context/`.
- `docs/architecture/auto.md` and `webapp.md` are cited from the code by
  section number. Add new sections at the end; never renumber.
- Write or update `.claude/context/NEXT_SESSION.md` only when the user says
  so. Do not refresh it at the end of a piece of work.
