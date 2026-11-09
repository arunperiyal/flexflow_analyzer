"""Help for `auto`."""


def print_auto_help():
    from src.utils.colors import Colors
    c, y, b, r = Colors.CYAN, Colors.YELLOW, Colors.BOLD, Colors.RESET
    print(f"""
{b}{c}auto — check every case in this folder and do its next safe step{r}

{b}USAGE:{r}
    auto init              write .auto.conf here, for you to check and edit
         [--remote NAME]   the remote (default: use remote:NAME); `local` for a folder
         [--path DIR]      the folder there (default: the remote's `remote set-path`)
         [--keep-rst N]    keep the .rst of steps divisible by N when thinning
         [--disk-alert SIZE]  flag running cases bigger than SIZE (e.g. 200G)
         [--force]         replace an existing .auto.conf
    auto show [case]       what auto would do, case by case; changes nothing
    auto apply [case]      carry it out {Colors.GRAY}(not built yet){r}
    auto log [case]        what earlier runs did {Colors.GRAY}(not built yet){r}

{b}WHAT IT LOOKS AT{r} (docs/AUTO_PLAN.md, Help -> Flowchart)
    The cases in this folder's .cases; the queue (squeue, sacct), each job
    matched to its case by the folder it was submitted from; the history,
    .out, .rst and PLT files; and what is already on the remote.

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

{b}SETTINGS{r}: {c}.auto.conf{r} next to .cases ({c}auto init{r} writes one to edit)
    remote     = cloud        a remote from `remote list` (or `local`: a folder)
    path       = /shares/...  the folder there; a case goes to <path>/<case>
    keep_rst   = 500          .rst grid kept when thinning (unset: no thinning)
    disk_alert = 200G         flag running cases whose run directory is bigger
    qos / account / partition only if set: passed to post jobs

{b}EXIT CODE{r}: 0 nothing needs you; 1 a case needs you, or the queue could
    not be read; 2 bad usage or no .auto.conf
""")
