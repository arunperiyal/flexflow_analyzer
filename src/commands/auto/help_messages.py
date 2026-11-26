"""Help for `auto`."""


def print_auto_help():
    from src.utils.colors import Colors
    c, y, b, r, g = Colors.CYAN, Colors.YELLOW, Colors.BOLD, Colors.RESET, Colors.GRAY
    print(f"""
{b}{c}auto — check every case in this folder and do its next safe step{r}

{b}USAGE:{r}
    auto init [--remote NAME] [--path DIR] [--keep-rst N] [--keep-newest-rst N] [--upload-rst N] [--disk-alert SIZE] [--vtu-cache keep|delete] [--force]
        set, in this folder's .cases.yml, the remote's folder for these cases
        (default: the remote's `remote set-path`) and auto's settings
    auto show [--case NAME] [--remote NAME] [--detail] [--only SECTIONS]
        what auto would do; changes nothing. case: a folder, or `use case:`;
        `use case:*` (or '*') for every case in .cases.yml. One case: labelled
        sections (State, History, PLT files, OUT files, RST files, Inputs and
        case files) with sizes, times and numbered Action commands. Every
        Action is a command you can run as it is, in the order `auto apply`
        takes them: check, post, upload, then the deletes (PLT files: `case
        check plt --verify`, `run post`, `case upload plt`, `case organise
        plt ascii`, `binary`). What is not a command is a
        row: Waiting (a job to end first), Why, Delete and Thin (what the
        delete commands will take), By hand. Several
        cases: the summary table; each in full with --detail. --only plt,rst
        shows just those sections (state, needs, flags, history, plt, out, rst,
        inputs).
    auto commands [--case NAME]   just the Action commands, numbered, as plain text
                           (`auto commands --case '*' > todo.sh` to read before running)
    auto status [--case NAME] [--only needs|todo|running|all]
                           one line per case: state, steps, jobs (with ids), what is next;
                           a footer counts the cases and those that need you. The cases
                           picked by --only (default all: needs = need you, todo = have
                           something to do, running = have a job in the queue) go to a
                           command after a `|`, which runs once for each:
                               auto status --case * --only needs | case show
                               auto status --case * --only todo | auto apply plt
                           the second command still asks its own questions (auto apply
                           asks per case unless --yes). Needs shellkit 0.1.8
    auto apply <target> [--case NAME] [--remote NAME] [--delete] [--dry-run] [--yes]
        target: history, plt, output, input, rst or all. With no target nothing
        is done and the targets are listed. A target word is always a target
        (a case of that name: ./plt). --only history,upload,post still works
        and means `all` limited to those steps (deprecated; `delete` is one of them).
        does the additive steps of the target for each case, in this order, planned again
        from the files and the queue right before each: organise the history
        (when no main job is active), upload what the remote lacks (to a
        temporary name, checked by md5, then renamed; the verified files are
        recorded in auto_logs/ledger.json), submit a post job for the first
        stretch with no PLT yet. It shows what it will do and asks once
        (--yes skips; --dry-run only shows). Without --delete it deletes
        nothing. --delete (or --only delete) adds the delete stage, between
        upload and post: the ASCII PLT, binary PLT and .out of a step whose
        copy on the remote passes an md5 check made right then (each file is
        checked again just before it goes), and the .rst sets off the
        keep_rst grid (no copy needed; the question gives their number and
        size). Nothing is deleted for a case that needs you, has a post job
        in the queue, or whose queue or remote could not be read. A step that
        fails stops that case; the others go on. The record of the run is
        auto_logs/auto_<time>.log.
        Without --delete it deletes nothing: `auto show` lists the delete
        commands for you to run. --delete (or --only delete) adds the delete
        stage between upload and post, for the files of the target: the
        ASCII PLT, binary PLT and .out of a step whose copy on the remote
        passes an md5 check made right then (each file is checked again just
        before it goes), and the .rst sets off the keep_rst grid (no copy
        needed; the question gives their number and size). Nothing is deleted
        for a case that needs you, has a post job in the queue, or whose queue
        or remote could not be read.
    auto log [--case NAME] [--list] [--log N]
                           read back the logs of `auto apply` (auto_logs/auto_<time>.log):
                           the newest run, one line per action, failures in red; with a
                           case only its lines. --list shows every run, one line each;
                           --log N reads the Nth newest (1 is the newest). The folder is the
                           shell's directory, or the one above it when it is a case.

    The remote is --remote NAME or `use remote:NAME`: its login comes from
    `remote list`, its folder for these cases from .cases.yml.

{b}WHAT IT LOOKS AT{r} (docs/architecture/auto.md, Help -> Flowchart)
    The queue (squeue, sacct), each job matched to its case by the folder it
    was submitted from; the history, .out, .rst and PLT files; and what is
    already on the remote.

{b}WHAT A CASE CAN GET{r}
    {y}history{r}   organise history update clean compile, when no main job
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
      vtu_cache: delete        the .vtu caches `field render` leaves in binary/: `keep` (the
                               default) deletes only a killed render's leftovers (.partial,
                               .deriving, a day old), `delete` also the caches whose PLT is
                               here; one whose PLT is gone is never deleted
      qos / account / partition  only if set: passed to post jobs

{b}EXIT CODE{r}: 0 nothing needs you; 1 a case needs you, or the queue could
    not be read; 2 bad usage, no .cases.yml, or no remote chosen
""")
