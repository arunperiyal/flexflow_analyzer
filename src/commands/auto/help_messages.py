"""Help for `auto`."""


def print_auto_help():
    from src.utils.colors import Colors
    c, y, b, r, g = Colors.CYAN, Colors.YELLOW, Colors.BOLD, Colors.RESET, Colors.GRAY
    print(f"""
{b}{c}auto — check every case in this folder and do its next safe step{r}

{b}USAGE:{r}
    auto init [--remote NAME] [--path DIR] [--keep-rst N] [--keep-newest-rst N] [--upload-rst N] [--disk-alert SIZE] [--force]
        set, in this folder's .cases.yml, the remote's folder for these cases
        (default: the remote's `remote set-path`) and auto's settings
    auto show [case] [--remote NAME] [--detail] [--only SECTIONS]
        what auto would do; changes nothing. case: a folder, or `use case:`;
        `use case:*` (or '*') for every case in .cases.yml. One case: labelled
        sections (State, History, PLT files, OUT files, RST files, Inputs and
        case files) with sizes, times and numbered Action commands. Several
        cases: the summary table; each in full with --detail. --only plt,rst
        shows just those sections (state, needs, flags, history, plt, out, rst,
        inputs).
    auto commands [case]   just the Action commands, numbered, as plain text
                           (`auto commands '*' > todo.sh` to read before running)
    auto status [case]     one line per case: state, steps, jobs, what is next
    auto apply [case] [--remote NAME] [--only history,upload,post] [--dry-run] [--yes]
        does the additive steps for each case, in this order, planned again
        from the files and the queue right before each: organise the history
        (when no main job is active), upload what the remote lacks (to a
        temporary name, checked by md5, then renamed; the verified files are
        recorded in auto_logs/ledger.json), submit a post job for the first
        stretch with no PLT yet. It shows what it will do and asks once
        (--yes skips; --dry-run only shows). It deletes nothing. A step that
        fails stops that case; the others go on. The record of the run is
        auto_logs/auto_<time>.log. Deletions (.out, PLTs, .rst) are not built.
    auto log [case]        {g}(not built yet; the logs are in auto_logs/){r}

    The remote is --remote NAME or `use remote:NAME`: its login comes from
    `remote list`, its folder for these cases from .cases.yml.

{b}WHAT IT LOOKS AT{r} (docs/architecture/auto.md, Help -> Flowchart)
    The queue (squeue, sacct), each job matched to its case by the folder it
    was submitted from; the history, .out, .rst and PLT files; and what is
    already on the remote.

{b}WHAT A CASE CAN GET{r}
    {y}history{r}   organise history --update --clean --compile, when no main job
              of the case is running, pending or completing
    {y}post{r}      run post for the newest run's steps whose PLT is neither on the
              remote nor whole here, when their .out are all there
    {y}upload{r}    history, binary PLTs, the newest restart set, inputs and
              program files the remote lacks (or holds at another size)
    {y}delete{r}    ASCII/binary PLTs and .out once the remote copy is checked;
              .rst thinned to keep_rst (never a restart point)
    {y}needs you{r} anything auto will not guess: a failed job, holes on the
              remote, a pruned archive/, a run stopped with nothing queued

{b}SETTINGS{r}: {c}.cases.yml{r}, in each case's parent folder
    remotes:
      cloud: /shares/...       the folder there; a case goes to <folder>/<case>
    auto:
      keep_rst: 500            .rst kept here when thinning, to resume after a failure
                               (unset: no thinning)
      keep_newest_rst: 2       thinning also keeps the N newest complete sets (default 2: if
                               the newest was cut short by a killed job, the one before it
                               restarts the run)
      upload_rst: 1000         .rst uploaded, to resume in the future: steps divisible by
                               this, plus a finished run's final set (a multiple of
                               keep_rst; unset: no restart sets uploaded)
      disk_alert: 200G         flag running cases whose run directory is bigger
      qos / account / partition  only if set: passed to post jobs

{b}EXIT CODE{r}: 0 nothing needs you; 1 a case needs you, or the queue could
    not be read; 2 bad usage, no .cases.yml, or no remote chosen
""")
