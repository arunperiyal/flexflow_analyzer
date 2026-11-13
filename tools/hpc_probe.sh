#!/bin/bash
# =============================================================================
# hpc_probe.sh -- answer the open questions of docs/architecture/auto.md on the cluster
# =============================================================================
# Read-only. It lists, counts and stats files; it reads at most the first
# 8 bytes of a few PLT files, the tail of each live .othd, and checksums ONE
# binary PLT (to time it). It never deletes or edits anything in a case. The
# only file it creates in the cases directory is a tiny clock-check file,
# removed at once (skip with NO_CLOCK_CHECK=1).
#
# Usage (on the HPC login node):
#   bash hpc_probe.sh [CASES_DIR] [REMOTE ...]
#
#   CASES_DIR  directory holding the cases (and .cases); default: .
#   REMOTE     extra ssh targets to test (user@host or a ~/.ssh/config Host);
#              the remotes in ~/.flexflow/remotes.json are tested too.
#              Only key login is tried (BatchMode): it never asks a password.
#
# Env:  MAX_CASES=12   how many cases to look at in detail
#       ONLY=remotes   only the follow-up checks and the remotes (quick)
#       ONLY=node      can auto work from this node: files, SLURM, network,
#                      cloud key + password login, timed test upload (SIZE_MB=50,
#                      to a temp file in the remote path, deleted after)
#       ONLY=job       submit ONLY=node as a 1-core 15-min job on shared
#                      (PROBE_PARTITION=..., WAIT=1 to wait for it)
#       PROBE_REMOTE=cloud  the remote for the login/upload test
#
# Output goes to the screen and to ~/flexflow_probe_<host>_<time>.txt.
# Bring that file back (or paste it) -- it holds no passwords.
# =============================================================================

set -u
CASES_DIR=$(cd "${1:-.}" 2>/dev/null && pwd) || { echo "No such directory: ${1:-.}"; exit 2; }
shift || true
EXTRA_REMOTES=("$@")
MAX_CASES=${MAX_CASES:-12}
REPORT="$HOME/flexflow_probe_$(hostname -s)_$(date +%Y%m%d_%H%M).txt"

exec > >(tee "$REPORT") 2>&1

# Be gentle on a shared login node
renice -n 15 $$ >/dev/null 2>&1
command -v ionice >/dev/null 2>&1 && ionice -c3 -p $$ >/dev/null 2>&1

hr()  { printf '\n==================== %s ====================\n' "$*"; }
sub() { printf '\n--- %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
run() {  # run CMD...: show it, its output (capped) and its exit code
    printf '$ %s\n' "$*"
    local out rc
    out=$(timeout 60 "$@" 2>&1); rc=$?
    printf '%s\n' "$out" | head -40
    [ "$(printf '%s\n' "$out" | wc -l)" -gt 40 ] && echo "  ... (cut)"
    echo "  [exit $rc]"
}
cfg() {  # cfg FILE KEY: value of 'key = value' in simflow.config
    grep -oP "^\s*$2\s*=\s*\"?\K[^\"#\s]+" "$1" 2>/dev/null | head -1
}

hr "probe"
echo "date      $(date '+%F %T %Z')"
echo "host      $(hostname -f 2>/dev/null || hostname)"
echo "user      $USER"
echo "cases dir $CASES_DIR"
echo "report    $REPORT"

# =============================================================================
# ONLY=node: can `auto` work from where this runs? (login node or, through
# ONLY=job, a compute node). ONLY=job: run ONLY=node inside a SLURM job.
# =============================================================================
# flexflow's own python: the launcher activates a conda env and runs main.py
find_py() {
    local ff env_name base
    ff=$(command -v flexflow) || return 1
    FLEXFLOW_DIR=$(grep -oP '^FLEXFLOW_DIR="?\K[^"]+' "$ff" | head -1)
    env_name=$(grep -oP '^CONDA_ENV="?\K[^"]+' "$ff" | head -1)
    for base in "$HOME/.conda" "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/miniforge3" \
                "$HOME/mambaforge" /home/apps/anaconda3; do
        [ -x "$base/envs/$env_name/bin/python" ] && { echo "$base/envs/$env_name/bin/python"; return 0; }
    done
    return 1
}

# Password login (from remotes.json, as `case upload` does) and a timed test
# upload: SIZE_MB of random bytes to <remote path>/.flexflow_probe_<host>_<pid>,
# md5 compared on both sides, then the file is deleted again.
PW_TEST=$(cat <<'EOF'
import hashlib, json, os, posixpath, socket, sys, tempfile, time
name, size_mb = sys.argv[1], int(sys.argv[2])
try:
    import paramiko
except ImportError as e:
    print("  paramiko missing:", e); sys.exit(1)
cfg = json.load(open(os.path.expanduser("~/.flexflow/remotes.json")))
r = next((x for x in cfg.get("remotes", []) if x.get("name") == name), None)
if r is None:
    print(f"  remote '{name}' is not in remotes.json"); sys.exit(1)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
t0 = time.time()
try:
    c.connect(r["ip"], port=int(r.get("port") or 22), username=r["user"],
              password=r.get("password"), timeout=15, banner_timeout=30,
              auth_timeout=30, look_for_keys=False, allow_agent=False)
except Exception as e:
    print(f"  password login FAILED: {type(e).__name__}: {e}"); sys.exit(2)
print(f"  password login ok ({time.time() - t0:.1f} s)")

def sh(cmd):
    _, o, e = c.exec_command(cmd, timeout=300)
    out = o.read().decode(errors="replace").strip()
    return o.channel.recv_exit_status(), out

base = r.get("path") or "."
if base.startswith("~"):
    base = sh("echo $HOME")[1] + base[1:]
if size_mb <= 0:
    sys.exit(0)
fd, local = tempfile.mkstemp(prefix="flexflow_probe_")
md5 = hashlib.md5()
with os.fdopen(fd, "wb") as f:
    for _ in range(size_mb):
        block = os.urandom(1 << 20)
        md5.update(block)
        f.write(block)
remote = posixpath.join(base, f".flexflow_probe_{socket.gethostname()}_{os.getpid()}")
try:
    sftp = c.open_sftp()
    t0 = time.time()
    sftp.put(local, remote + ".part")
    dt = time.time() - t0
    sftp.posix_rename(remote + ".part", remote)
    print(f"  upload {size_mb} MB: {dt:.1f} s = {size_mb / dt:.1f} MB/s ({size_mb * 8 / dt:.0f} Mbps)")
    t0 = time.time()
    rc, out = sh(f"md5sum '{remote}'")
    mt = time.time() - t0
    there = out.split()[0] if rc == 0 and out else None
    print(f"  remote md5sum of {size_mb} MB: {mt:.1f} s = {size_mb / mt:.1f} MB/s")
    print("  md5 " + ("MATCHES" if there == md5.hexdigest() else f"DIFFERS ({there} vs {md5.hexdigest()})"))
except Exception as e:
    print(f"  test upload FAILED: {type(e).__name__}: {e}")
finally:
    sh(f"rm -f '{remote}' '{remote}.part'")
    left = sh(f"ls '{remote}' '{remote}.part' 2>/dev/null")[1]
    print("  test file " + ("NOT removed: " + left if left else "removed"))
    os.unlink(local)
    c.close()
EOF
)

if [ "${ONLY:-}" = node ]; then
    hr "Can auto work from $(hostname -s)?  (${SLURM_JOB_ID:+job $SLURM_JOB_ID, }${SLURM_JOB_PARTITION:-not in a job})"
    sub "files auto needs"
    for f in "$HOME/.flexflow/remotes.json" "$HOME/.ssh/config" "$CASES_DIR/.cases"; do
        if [ -r "$f" ]; then echo "  readable  $f"; else echo "  NOT readable  $f"; fi
    done
    [ -w "$CASES_DIR" ] && echo "  writable  $CASES_DIR" || echo "  NOT writable  $CASES_DIR"
    py=$(find_py) || py=""
    FLEXFLOW_DIR=$(grep -oP '^FLEXFLOW_DIR="?\K[^"]+' "$(command -v flexflow)" 2>/dev/null | head -1)
    if [ -n "$py" ]; then
        echo "  flexflow python: $py ($($py --version 2>&1))"
        (cd "${FLEXFLOW_DIR:-.}" && $py -c 'import paramiko, rich, src.utils.remote_config; print("  flexflow modules import ok")' 2>&1 | tail -1)
    else
        echo "  flexflow python NOT found (command -v flexflow: $(command -v flexflow || echo none))"
    fi
    sub "SLURM from here (auto reads the queue; a job could resubmit itself)"
    for t in squeue sacct sbatch; do printf '  %-7s %s\n' $t "$(command -v $t || echo -)"; done
    out=$(squeue -h -u "$USER" -o '%i' 2>&1); echo "  squeue: exit $?, $(printf '%s\n' "$out" | grep -c .) line(s)"
    out=$(sacct -u "$USER" -X -S now-1days -n -P --format=JobID 2>&1); echo "  sacct: exit $?, $(printf '%s\n' "$out" | grep -c .) line(s)"
    out=$(sbatch --test-only -p shared -n 1 -t 00:01:00 --wrap=true 2>&1); echo "  sbatch --test-only (submits nothing): exit $?  $(printf '%s' "$out" | head -1)"
    sub "network: TCP to port 22 of each remote"
    if have python3 && [ -r "$HOME/.flexflow/remotes.json" ]; then
        python3 -c '
import json, os
for r in json.load(open(os.path.expanduser("~/.flexflow/remotes.json"))).get("remotes", []):
    print(r.get("name"), r.get("ip"), r.get("port") or 22)' 2>/dev/null |
        while read -r rn ip port; do
            if timeout 6 bash -c "</dev/tcp/$ip/$port" 2>/dev/null; then r=open; else r="CLOSED/unreachable"; fi
            printf '  %-12s %s:%s  %s\n' "$rn" "$ip" "$port" "$r"
        done
    fi
    PROBE_REMOTE=${PROBE_REMOTE:-cloud}
    sub "$PROBE_REMOTE: key login through the ssh alias"
    timeout 30 ssh -o BatchMode=yes -o ConnectTimeout=10 "$PROBE_REMOTE" \
        'echo "  key login ok"; echo x | md5sum >/dev/null && echo "  md5sum ok"' 2>&1 | head -5
    echo "  [exit ${PIPESTATUS[0]}]"
    sub "$PROBE_REMOTE: password login from remotes.json + ${SIZE_MB:-50} MB test upload"
    if [ -n "${py:-}" ]; then
        (cd /tmp && timeout 600 $py -c "$PW_TEST" "$PROBE_REMOTE" "${SIZE_MB:-50}") 2>&1 | head -20
    else
        echo "  skipped: no flexflow python"
    fi
    hr "done"
    echo "Report saved: $REPORT"
    exit 0
fi

if [ "${ONLY:-}" = job ]; then
    hr "submitting the probe as a SLURM job"
    mkdir -p "$HOME/.flexflow_probe"
    cp "$(readlink -f "$0")" "$HOME/.flexflow_probe/hpc_probe.sh"
    js="$HOME/.flexflow_probe/probe_job.sh"
    cat > "$js" <<EOF
#!/bin/bash
#SBATCH -J probeFlexflow
#SBATCH -p ${PROBE_PARTITION:-shared}
#SBATCH -n 1
#SBATCH -t 00:15:00
#SBATCH -o $HOME/flexflow_probe_job_%j.txt
ONLY=node PROBE_REMOTE=${PROBE_REMOTE:-cloud} SIZE_MB=${SIZE_MB:-50} bash "$HOME/.flexflow_probe/hpc_probe.sh" "$CASES_DIR"
EOF
    echo "job script: $js"
    out=$(sbatch ${WAIT:+--wait} "$js" 2>&1); rc=$?
    echo "$out"
    id=$(printf '%s' "$out" | grep -oE '[0-9]+' | head -1)
    if [ $rc -eq 0 ] && [ -n "$id" ]; then
        echo "result will be in: $HOME/flexflow_probe_job_${id}.txt"
        [ -n "${WAIT:-}" ] && cat "$HOME/flexflow_probe_job_${id}.txt"
    fi
    exit 0
fi

# -----------------------------------------------------------------------------
if [ "${ONLY:-}" != remotes ]; then
hr "Q3  running unattended: cron / scrontab / tmux"
# -----------------------------------------------------------------------------
for t in crontab scrontab tmux screen nohup setsid at systemd-run; do
    printf '%-12s %s\n' "$t" "$(command -v $t || echo '-')"
done
if have crontab; then
    out=$(crontab -l 2>&1); rc=$?
    echo "crontab -l: exit $rc, $(printf '%s\n' "$out" | grep -vc '^\s*#') non-comment line(s)"
    printf '%s\n' "$out" | grep -i 'not allowed\|permission\|denied' | head -3
fi
for f in /etc/cron.allow /etc/cron.deny; do
    [ -e "$f" ] && echo "$f exists$( [ -r "$f" ] && grep -qx "$USER" "$f" && echo ", lists you")"
done
if have scrontab; then
    out=$(scrontab -l 2>&1); echo "scrontab -l: exit $?"; printf '%s\n' "$out" | head -5
fi
echo "TMOUT=${TMOUT:-unset}  (shell idle logout)"
echo "ulimit -t (cpu seconds per process): $(ulimit -t)"
grep -i 'ClientAliveInterval\|ClientAliveCountMax' /etc/ssh/sshd_config 2>/dev/null | grep -v '^#'

# -----------------------------------------------------------------------------
hr "Q5  SLURM: limits, accounting, and how squeue fails"
# -----------------------------------------------------------------------------
for t in squeue sbatch scontrol sacct sinfo sacctmgr sshare; do
    printf '%-10s %s\n' "$t" "$(command -v $t || echo '-')"
done
if have squeue; then
    sub "your jobs, with WorkDir (%Z) -- auto matches jobs to cases by this"
    run squeue -u "$USER" -h -o '%i|%j|%T|%P|%Z'
    sub "an invalid job id: does squeue fail loudly (exit code / stderr)?"
    run squeue -h -j 999999999
    sub "squeue for a user that does not exist"
    run squeue -h -u no_such_user_xyz
fi
if have sacct; then
    sub "sacct, last 3 days (finished jobs and how they ended)"
    run sacct -u "$USER" -X -S now-3days -P -n --format=JobID,JobName%40,State,ExitCode,Elapsed,End
    sub "sacct retention: jobs visible over 30 days"
    echo "$(sacct -u "$USER" -X -S now-30days -n -P --format=JobID 2>/dev/null | wc -l) job(s)"
fi
if have sacctmgr; then
    sub "your associations (per-user job limits)"
    run sacctmgr -n -P show assoc user="$USER" format=Account,Partition,QOS,MaxJobs,MaxSubmit,MaxWall,GrpTRES
    sub "QOS limits"
    run sacctmgr -n -P show qos format=Name,MaxJobsPU,MaxSubmitPU,MaxWall,MaxTRESPU
fi
have sinfo && { sub "partitions"; run sinfo -s; }
if have scontrol; then
    sub "how long finished jobs stay visible to squeue/scontrol"
    scontrol show config 2>/dev/null | grep -iE 'MinJobAge|ScronParameters|MaxJobCount' || echo "(scontrol show config gave nothing)"
fi

# -----------------------------------------------------------------------------
hr "Tools on this node"
# -----------------------------------------------------------------------------
for t in python3 rsync sha256sum md5sum flock ssh timeout stat awk find; do
    v=$(command -v $t) || { printf '%-10s -\n' "$t"; continue; }
    case $t in
        python3) v="$v  $(python3 --version 2>&1)" ;;
        rsync)   v="$v  $(rsync --version 2>/dev/null | head -1)" ;;
        ssh)     v="$v  $(ssh -V 2>&1)" ;;
        stat)    stat -c %s / >/dev/null 2>&1 && v="$v  (GNU stat -c works)" ;;
    esac
    printf '%-10s %s\n' "$t" "$v"
done
have flexflow && echo "flexflow   $(command -v flexflow)"

# -----------------------------------------------------------------------------
hr "Filesystem under the cases (mtime trust)"
# -----------------------------------------------------------------------------
df -hT "$CASES_DIR" 2>/dev/null
if [ "${NO_CLOCK_CHECK:-0}" != 1 ]; then
    f="$CASES_DIR/.flexflow_probe_clock_$$"
    if : > "$f" 2>/dev/null; then
        now=$(date +%s); m=$(stat -c %Y "$f"); rm -f "$f"
        echo "clock skew, file server minus this node: $((m - now)) s"
    else
        echo "could not write a clock-check file in $CASES_DIR"
    fi
fi
have lfs && { sub "lustre quota"; run lfs quota -h -u "$USER" "$CASES_DIR"; }
have quota && { sub "quota"; run quota -s; }

# -----------------------------------------------------------------------------
hr "Q1  cases: .out/.rst naming and parts per step, PLTs, history"
# -----------------------------------------------------------------------------
# Case list: the paths in .cases, else the subdirectories with a simflow.config
CASES=()
if [ -f "$CASES_DIR/.cases" ]; then
    while IFS= read -r p; do [ -d "$p" ] && CASES+=("$p"); done < <(
        grep -oP '"path"\s*:\s*"\K[^"]+' "$CASES_DIR/.cases")
    echo ".cases lists ${#CASES[@]} existing case(s)"
fi
if [ ${#CASES[@]} -eq 0 ]; then
    while IFS= read -r c; do CASES+=("$(dirname "$c")"); done < <(
        find "$CASES_DIR" -mindepth 2 -maxdepth 2 -name simflow.config | sort)
    echo "found ${#CASES[@]} case(s) with simflow.config"
fi

n=0
for case in "${CASES[@]}"; do
    n=$((n + 1)); [ $n -gt "$MAX_CASES" ] && { echo; echo "(stopping at MAX_CASES=$MAX_CASES)"; break; }
    name=$(basename "$case")
    sub "case $name"
    conf="$case/simflow.config"
    [ -f "$conf" ] || { echo "  no simflow.config"; continue; }
    p=$(cfg "$conf" problem); np=$(cfg "$conf" np); nsg=$(cfg "$conf" nsg)
    freq=$(cfg "$conf" outFreq); rdir=$(cfg "$conf" dir)
    rflag=$(cfg "$conf" restartFlag); rts=$(cfg "$conf" restartTsId)
    maxs=$(grep -oP 'maxTimeSteps\s*=\s*\K\d+' "$case/$p.def" 2>/dev/null | head -1)
    echo "  problem=$p np=$np nsg=$nsg outFreq=$freq dir=$rdir restartFlag=${rflag:-} restartTsId=${rts:-} maxTimeSteps=${maxs:-?}"
    run_dir="$case/${rdir#./}"
    [ -n "$rdir" ] && [ -d "$run_dir" ] || { echo "  run dir not found: $run_dir"; run_dir=""; }

    if [ -n "$run_dir" ]; then
        for ext in out rst; do
            # step part size mtime, one line per file named <p>.<step>_<k>.<ext>
            find "$run_dir" -maxdepth 1 -type f -name "$p.*_*.$ext" -printf '%f %s %T@\n' 2>/dev/null \
            | awk -v p="$p" -v ext="$ext" -v nsg="${nsg:-0}" -v np="${np:-0}" '
                { name = $1; sub("^" p "\\.", "", name); sub("\\." ext "$", "", name)
                  split(name, a, "_")
                  if (a[1] !~ /^[0-9]+$/ || a[2] !~ /^[0-9]+$/) { odd++; next }
                  s = a[1] + 0; k = a[2] + 0
                  cnt[s]++; if (!(s in kmin) || k < kmin[s]) kmin[s] = k; if (k > kmax[s]) kmax[s] = k
                  if ($2 == 0) zero++
                  if ($3 > newest[s]) newest[s] = $3
                  files++ }
                END {
                  if (!files) { printf "  .%s: none\n", ext; exit }
                  ns = 0; for (s in cnt) { st[++ns] = s + 0; hist[cnt[s]]++ ; lo = (lo == "" || kmin[s] < lo) ? kmin[s] : lo; if (kmax[s] > hi) hi = kmax[s] }
                  # sort steps
                  for (i = 2; i <= ns; i++) { v = st[i]; j = i - 1; while (j > 0 && st[j] > v) { st[j+1] = st[j]; j-- } st[j+1] = v }
                  printf "  .%s: %d file(s), %d step(s) %d..%d, part index %d..%d, zero-size %d, odd names %d\n", ext, files, ns, st[1], st[ns], lo, hi, zero + 0, odd + 0
                  printf "    parts per step (count: steps):"; for (c in hist) printf " %d:%d", c, hist[c]; printf "   [nsg=%s np=%s]\n", nsg, np
                  # time between consecutive steps (last 20)
                  m = 0; from = (ns > 21) ? ns - 20 : 2
                  for (i = from; i <= ns; i++) { d = newest[st[i]] - newest[st[i-1]]; if (d > 0) { gap[++m] = d } }
                  if (m) { for (i = 2; i <= m; i++) { v = gap[i]; j = i - 1; while (j > 0 && gap[j] > v) { gap[j+1] = gap[j]; j-- } gap[j+1] = v }
                           printf "    seconds between steps (last %d): min %.0f, median %.0f, max %.0f\n", m, gap[1], gap[int((m+1)/2)], gap[m] }
                  printf "    newest step written %.0f s ago\n", systime() - newest[st[ns]]
                  # incomplete steps, newest first
                  printf "    steps with a part count other than the most common:"
                  best = 0; for (c in hist) if (hist[c] > best) { best = hist[c]; mode = c }
                  shown = 0; for (i = ns; i >= 1 && shown < 10; i--) if (cnt[st[i]] != mode) { printf " %d(%d)", st[i], cnt[st[i]]; shown++ }
                  print (shown ? "" : " none")
                }'
        done
        other=$(find "$run_dir" -maxdepth 1 -type f -name '*.out' ! -name "$p.*_*.out" -printf '%f\n' 2>/dev/null | head -5 | tr '\n' ' ')
        [ -n "$other" ] && echo "  other .out names in run dir: $other"
        np_ascii=$(find "$run_dir" -maxdepth 1 -type f -name "$p.*.plt" | wc -l)
        echo "  ASCII .plt in run dir: $np_ascii"
        if [ -f "$run_dir/$p.othd" ]; then
            last=$(tail -c 2000000 "$run_dir/$p.othd" | grep '^tsId ' | tail -1 | awk '{print $2}')
            age=$(( $(date +%s) - $(stat -c %Y "$run_dir/$p.othd") ))
            echo "  live $p.othd: $(stat -c %s "$run_dir/$p.othd") B, last tsId ${last:-?}, changed ${age}s ago"
        fi
    fi

    if [ -d "$case/binary" ]; then
        echo "  binary/: $(find "$case/binary" -maxdepth 1 -name "$p.*.plt" | wc -l) plt, $(find "$case/binary" -maxdepth 1 -name '*.vtu' | wc -l) vtu"
        echo "    sizes (bytes: files), most common first:"
        find "$case/binary" -maxdepth 1 -type f -name "$p.*.plt" -printf '%s\n' | sort | uniq -c | sort -rn | head -6 \
            | awk '{printf "      %s: %s\n", $2, $1}'
        for f in $(ls "$case/binary"/$p.*.plt 2>/dev/null | sort -t. -k2,2n | sed -n '1p;$p' | uniq); do
            printf '    header of %s: %s\n' "$(basename "$f")" "$(head -c 8 "$f" | tr -c '[:print:]' '?')"
        done
        small=$(find "$case/binary" -maxdepth 1 -type f -name "$p.*.plt" -printf '%s %p\n' | sort -n | head -1 | cut -d' ' -f2-)
        [ -n "$small" ] && printf '    smallest %s: %s B, header %s\n' "$(basename "$small")" "$(stat -c %s "$small")" "$(head -c 8 "$small" | tr -c '[:print:]' '?')"
    else
        echo "  no binary/"
    fi

    for h in othd_files oisd_files rcv_files; do
        [ -d "$case/$h" ] && echo "  $h: $(find "$case/$h" -type f -printf '%P (%s B)  ' | head -c 400)"
    done
    echo "  markers: .post_start_* $(ls -a "$case" | grep -c '^\.post_start_'), post_sent_*.log $(ls "$case" | grep -c '^post_sent_'), slurm-*.out $(ls "$case" | grep -c '^slurm-.*\.out$')"
    for s in postFlex.sh mainFlex.sh; do
        [ -f "$case/$s" ] || continue
        echo "  $s: $(grep -E '^#SBATCH +(-J|-p|-n|-t|-A|--account|--qos|--partition)' "$case/$s" | sed 's/#.*SBATCH *//; s/ *#.*//' | tr '\n' ';')"
    done
    grep -q REMOTE_TARGET "$case/postFlex.sh" 2>/dev/null && echo "  postFlex.sh can send to a remote"
    [ -f "$case/.casestatus.md" ] && { echo "  .casestatus.md: state$(grep -m1 "^state:" "$case/.casestatus.md" | cut -d: -f2), last log lines:"; grep '^- ' "$case/.casestatus.md" | tail -4 | sed 's/^/    /'; }
    [ -f "$case/.restarts" ] && { echo "  .restarts:"; grep -v '^#' "$case/.restarts" | sed 's/^/    /'; }
done

# One checksum, timed, to see what verifying costs on this node
pick=$(find "${CASES[@]:-$CASES_DIR}" -maxdepth 2 -path '*/binary/*.plt' -type f 2>/dev/null | head -1)
if [ -n "$pick" ] && have sha256sum; then
    sub "checksum cost on this node"
    sz=$(stat -c %s "$pick"); t0=$(date +%s.%N)
    nice -n 19 sha256sum "$pick" >/dev/null
    t1=$(date +%s.%N)
    awk -v s="$sz" -v a="$t0" -v b="$t1" 'BEGIN { d = b - a; printf "sha256 of %.0f MB took %.1f s (%.0f MB/s)\n", s/1e6, d, (d > 0 ? s/1e6/d : 0) }'
fi

# -----------------------------------------------------------------------------
fi  # ONLY=remotes skips everything above

# -----------------------------------------------------------------------------
hr "Follow-up: flexflow python, your QOS, at"
# -----------------------------------------------------------------------------
ff=$(command -v flexflow)
if [ -n "$ff" ]; then
    # The launcher is a bash wrapper that activates a conda env and runs main.py
    echo "launcher: $ff"
    grep -E '^(FLEXFLOW_DIR|CONDA_ENV)=|exec ' "$ff" | sed 's/^/  /'
    env_name=$(grep -oP '^CONDA_ENV="?\K[^"]+' "$ff" | head -1)
    py=""
    for base in "$HOME/.conda" "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/miniforge3" \
                "$HOME/mambaforge" /home/apps/anaconda3; do
        [ -n "$env_name" ] && [ -x "$base/envs/$env_name/bin/python" ] && { py="$base/envs/$env_name/bin/python"; break; }
    done
    if [ -z "$py" ] && [ -n "$env_name" ]; then
        # anywhere else conda keeps envs (envs_dirs in ~/.condarc)
        grep -A5 envs_dirs "$HOME/.condarc" 2>/dev/null | sed 's/^/  condarc: /'
        py=$(find "$HOME" /home/apps -maxdepth 5 -path "*/envs/$env_name/bin/python" 2>/dev/null | head -1)
    fi
    if [ -n "$py" ]; then
        echo "flexflow python: $py  ($($py --version 2>&1))"
        $py -c 'import paramiko, rich; print("  paramiko", paramiko.__version__)' 2>&1 | tail -1
    else
        echo "could not find the conda env '${env_name:-?}' python"
        echo "python that 'conda activate $env_name' gives:"
        (for c in "$HOME"/*/etc/profile.d/conda.sh /home/apps/anaconda3/etc/profile.d/conda.sh; do
             [ -f "$c" ] && { source "$c"; break; }; done
         conda activate "$env_name" 2>&1 | head -2; command -v python; python --version) 2>&1 | sed 's/^/  /'
    fi
fi
if have sacctmgr; then
    sub "your default account and the QOS of your associations"
    run sacctmgr -n -P show user "$USER" format=User,DefaultAccount
    qos=$(sacctmgr -n -P show assoc user="$USER" format=QOS | tr "\n" "," | sed "s/,*$//")
    [ -n "$qos" ] && run sacctmgr -n -P show qos "$qos" format=Name,MaxJobsPU,MaxSubmitPU,MaxWall,MaxTRESPU,GrpTRES,Priority
    sub "accounts your recent jobs ran under"
    run sacct -u "$USER" -X -S now-14days -n -P --format=JobName%30,Account,QOS,Partition,AllocCPUS
fi
for f in /etc/at.allow /etc/at.deny; do [ -e "$f" ] && echo "$f exists"; done
have atq && { out=$(atq 2>&1); echo "atq: exit $?  $out" | head -3; }

hr "Q2  remotes: key login and checksum tools"
# -----------------------------------------------------------------------------
TARGETS=()
if [ -f "$HOME/.flexflow/remotes.json" ] && have python3; then
    # name, user@ip and port only -- never the password
    while IFS='|' read -r rname target port path; do
        echo "remote '$rname': $target port ${port:-22} path ${path:-}"
        TARGETS+=("$target|${port:-22}|$rname|$path")
    done < <(python3 - "$HOME/.flexflow/remotes.json" <<'EOF'
import json, sys
data = json.load(open(sys.argv[1]))
items = data.get('remotes', data) if isinstance(data, dict) else data
if isinstance(items, dict):
    items = [dict(v, name=k) for k, v in items.items()]
for r in items:
    print(f"{r.get('name','?')}|{r.get('user','')}@{r.get('ip','')}|{r.get('port') or 22}|{r.get('path','')}")
EOF
)
else
    echo "no ~/.flexflow/remotes.json (or no python3)"
fi
[ -f "$HOME/.ssh/config" ] && echo "~/.ssh/config hosts: $(grep -iE '^\s*Host\s' "$HOME/.ssh/config" | awk '{for(i=2;i<=NF;i++) printf "%s ", $i}')"
for t in ${EXTRA_REMOTES[@]+"${EXTRA_REMOTES[@]}"}; do TARGETS+=("$t||$t|"); done
# shellcheck disable=SC2016
REMOTE_TEST='echo "uname: $(uname -sm)"; for t in sha256sum md5sum rsync python3 df stat mv; do printf "  %-10s %s\n" $t "$(command -v $t || echo -)"; done
echo x | sha256sum >/dev/null 2>&1 && echo "  sha256sum works" || echo "  sha256sum does NOT work"
echo x | md5sum >/dev/null 2>&1 && echo "  md5sum works" || echo "  md5sum does NOT work"
stat -c %s / >/dev/null 2>&1 && echo "  stat -c works" || echo "  stat -c does NOT work"
df -h . 2>/dev/null | tail -1'
for entry in ${TARGETS[@]+"${TARGETS[@]}"}; do
    IFS='|' read -r target port rname rpath <<<"$entry"
    sub "remote $rname ($target)"
    # An ssh config Host with the remote's name wins, as `run post --remote`
    # does: its User/IdentityFile are the ones the keys were set up for.
    if [ "$rname" != "$target" ] && grep -qiE "^\s*Host\s.*\b$rname\b" "$HOME/.ssh/config" 2>/dev/null; then
        via="$rname"; opts=(-o BatchMode=yes -o ConnectTimeout=10)
        echo "  via ssh alias '$rname': $(ssh -G "$rname" 2>/dev/null | grep -E '^(user|hostname|port|identityfile) ' | tr '\n' ' ')"
    else
        via="$target"; opts=(-o BatchMode=yes -o ConnectTimeout=10)
        [ -n "$port" ] && opts+=(-p "$port")
        echo "  direct (no ssh alias)"
    fi
    test_cmd="$REMOTE_TEST"
    if [ -n "$rpath" ]; then
        # the remote path from remotes.json: there? writable? space?
        test_cmd="$test_cmd
p='$rpath'; case \"\$p\" in '~/'*) p=\"\$HOME/\${p#\\~/}\" ;; esac
[ -d \"\$p\" ] && echo \"  path exists: \$p\" || echo \"  path MISSING: \$p\"
[ -w \"\$p\" ] && echo \"  path writable\" || echo \"  path NOT writable\"
df -h \"\$p\" 2>/dev/null | tail -1 | sed 's/^/  space at path: /'"
    fi
    timeout 40 ssh "${opts[@]}" "$via" "$test_cmd" 2>&1 | head -25
    echo "  [exit ${PIPESTATUS[0]}]  (255 = no key login / unreachable)"
done

hr "done"
echo "Report saved: $REPORT"
