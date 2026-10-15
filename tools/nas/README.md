# NAS case helpers

`simulation_functions.sh` checks and cleans case data on the NAS, where
flexflow itself cannot run (a BusyBox box: `ash`, no bash, no python). It is
plain POSIX `sh` plus the BusyBox tools (`awk`, `sed`, `grep`, `stat`).

| Function | Does |
|---|---|
| `show_plt [--t1 N] [--t2 N] [--freq N]` | Lists the missing and empty binary PLT files |
| `show_archive [--type othd\|oisd]` | The othd/oisd parts: size, steps, tsId range; marks redundant parts, restarts and gaps |
| `clean_archive --n N1:N2 [--type othd\|oisd]` | Deletes parts by number (`N`, `N1:N2`, `N1:`, `:N2`) |
| `clean_plt --t1 N --t2 N [--freq N]` | Deletes PLT files for steps t1..t2 (every freq-th with `--freq`) |

Each takes `--case DIR` (default: current directory) and `--problem NAME`.
`problem` and `outFreq` default to the case's `simflow.config`. `-h` on a
function shows its usage; `sf_help` lists them all.

The clean functions show what they would delete and ask first; `--dry-run`
only shows. Deleting a part that is not redundant, or every part of a type,
needs `DELETE` typed out.

## Install / update on the NAS

There is no scp server on the NAS, so copy it over ssh:

```bash
ssh cloud 'cat > ~/simulation_functions.sh' < tools/nas/simulation_functions.sh
```

then on the NAS: `. ~/simulation_functions.sh` (or `source`).

Tests: `test_scripts/test_nas_functions.py` runs it under `busybox ash`
(skipped where BusyBox is not installed).
