# NAS case helpers

`simulation_functions.sh` checks and cleans case data on the NAS, where
flexflow itself cannot run (a BusyBox box: `ash`, no bash, no python). It is
plain POSIX `sh` plus the BusyBox tools (`awk`, `sed`, `grep`, `stat`).

| Function | Does |
|---|---|
| `show_plt [--t1 N] [--t2 N] [--freq N] [--since DATE]` | Lists the missing and empty binary PLT files; with `--since`, the stale ones from before a restart |
| `show_archive [--type othd\|oisd]` | The othd/oisd parts: size, steps, tsId range; marks redundant parts, restarts and gaps |
| `clean_archive --n N1:N2 [--type othd\|oisd]` | Deletes parts by number (`N`, `N1:N2`, `N1:`, `:N2`) |
| `clean_plt --t1 N --t2 N [--freq N]` | Deletes PLT files for steps t1..t2 (every freq-th with `--freq`) |
| `missing [dir] [pattern] [--t1 N] [--t2 N] [--freq N] [--empty] [--extra] [-q]` | The gaps in a numbered series (`slice_xVor_{}.png`); with no pattern, every series in dir |

The case functions take `--case DIR` (default: current directory) and `--problem NAME`.
`problem` and `outFreq` default to the case's `simflow.config`. `-h` on a
function shows its usage; `sf_help` lists them all.

The clean functions show what they would delete and ask first; `--dry-run`
only shows. Deleting a part that is not redundant, or every part of a type,
needs `DELETE` typed out.

After a restart from `restartTsId` R the steps past R are computed again,
so a PLT of those steps made from the earlier run does not join up with the
frames around it. On the cluster `case check plt` finds them from the
resumed run's `.out`/`.rst` dates; the NAS has neither, and a PLT's date
there is when it arrived (it is sent with `ssh ... cat`). So `show_plt` needs
to be told when the resumed job started:

```sh
show_plt --case CS4SG3U1P0 --since '2026-10-20 14:00'     # sacct -j JOBID -o Start
```

A PLT past R that arrived before then is listed as `stale`. R is
`restartTsId` from `simflow.config` (when `restartFlag` is on), or
`--restart N`. A new PLT can only arrive after the job started, so nothing
good is flagged; an old one sent late can slip through.

`missing` is the flexflow shell's `missing` for any files: `{}` in the
pattern is the number, and the range and step default to the files found.
Without a pattern it checks each group of names that differ only in a
number (`riser.{}_0.out`, `riser.{}_1.out`, ... one per subgrid). In a pipe
it prints just the names (`missing post | wc -l`).

```sh
missing CS4SG3U1P0/post
missing CS4SG3U1P0/post 'slice_xVor_{}.png' --t1 3000 --t2 5000 --freq 50
```

## Install / update on the NAS

There is no scp server on the NAS, so copy it over ssh:

```bash
ssh cloud 'cat > ~/simulation_functions.sh' < tools/nas/simulation_functions.sh
```

then on the NAS: `. ~/simulation_functions.sh` (or `source`).

Tests: `test_scripts/test_nas_functions.py` runs it under `busybox ash`
(skipped where BusyBox is not installed).
