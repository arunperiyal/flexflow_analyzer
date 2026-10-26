#!/bin/bash
#SBATCH -J post{CASE_NAME}              # name of the job
#SBATCH -p shared                       # partition: standard, standard-low, gpu, hm, shared, medium
#SBATCH -n 36                           # number of processes/tasks
#SBATCH --cpus-per-task=1               # number of threads per process/task
#SBATCH -t 24:00:00                     # walltime in HH:MM:SS (Max: 72:00:00)

# =============================================================================
# FlexFlow Postprocessing Script Template
# =============================================================================
# This script runs postprocessing on simulation output:
#   1. simPlt - Converts .out files to ASCII PLT files
#   2. simPlt2Bin - Converts ASCII PLT to binary format
#   3. (with `run post --remote NAME`) sends each binary PLT to a remote
#      machine as soon as it is written, over ssh with key authentication
#
# The script auto-detects PROBLEM, RUN_DIR, and FREQ from simflow.config
# Command-line arguments can override these defaults
#
# Usage:
#   sbatch postFlex.sh [FREQ] [START_TIME] [END_TIME]
#
# Arguments:
#   FREQ       - Output frequency (optional, reads from config if not provided)
#   START_TIME - Start timestep (optional, default: 0)
#   END_TIME   - End timestep (optional, default: maxTimeSteps from .def file)
# =============================================================================

# Change to the submission directory (SLURM runs scripts from a temp location)
cd "$SLURM_SUBMIT_DIR"

# -----------------------------------------------------------------------------
# Load environment (paths to executables, modules)
# -----------------------------------------------------------------------------

source "${SLURM_SUBMIT_DIR}/simflow_env.sh"

# -----------------------------------------------------------------------------
# Parse simflow.config for default values
# -----------------------------------------------------------------------------

CONFIG_FILE="simflow.config"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: simflow.config not found in current directory"
    exit 1
fi

# Handles both: problem = riser  and  problem = "riser"
PROBLEM=$(grep -oP '^\s*problem\s*=\s*"?\K[^"#\s]+' "$CONFIG_FILE" | head -1)
if [ -z "$PROBLEM" ]; then
    echo "Error: Could not find 'problem' in simflow.config"
    exit 1
fi

# Extract run directory from config
# Handles both: dir = ./RUN_1  and  dir = "RUN_1"
RUN_DIR=$(grep -oP '^\s*dir\s*=\s*"?\K[^"#\s]+' "$CONFIG_FILE" | head -1)
if [ -z "$RUN_DIR" ]; then
    echo "Warning: Could not find 'dir' in simflow.config, using 'SIMFLOW_DATA'"
    RUN_DIR="SIMFLOW_DATA"
fi

# Extract output frequency from config (key is 'outFreq')
CONFIG_FREQ=$(grep -oP '^\s*outFreq\s*=\s*\K\d+' "$CONFIG_FILE" | head -1)
if [ -z "$CONFIG_FREQ" ]; then
    echo "Warning: Could not find 'outFreq' in simflow.config"
    CONFIG_FREQ=100  # Default fallback
fi

# Extract maxTimeSteps from the .def file (simPlt requires -last)
DEF_FILE="${PROBLEM}.def"
MAX_STEPS=""
if [ -f "$DEF_FILE" ]; then
    MAX_STEPS=$(grep -oP 'maxTimeSteps\s*=\s*\K\d+' "$DEF_FILE" | head -1)
fi
if [ -z "$MAX_STEPS" ]; then
    echo "Error: Could not find 'maxTimeSteps' in ${DEF_FILE} — simPlt requires -last"
    exit 1
fi

# -----------------------------------------------------------------------------
# Parse command-line arguments (override config values)
# -----------------------------------------------------------------------------

# FREQ: env var (from sbatch --export) > positional arg > config value
FREQ=${FREQ:-${1:-$CONFIG_FREQ}}

# START_TIME: env var > positional arg > 0
START_TIME=${START_TIME:-${2:-0}}

# END_TIME: env var > positional arg > maxTimeSteps from .def
END_TIME=${END_TIME:-${3:-$MAX_STEPS}}

# CONVERT_ONLY: skip simPlt and run only simPlt2Bin (env var, default: 0)
CONVERT_ONLY=${CONVERT_ONLY:-0}

# -----------------------------------------------------------------------------
# Case notes: .casestatus.md (`case status`)
# -----------------------------------------------------------------------------
# The job adds its own lines to the ## Log section: which steps it converted,
# how it ended. The state is the run's, so post leaves it alone. Never fatal.

CASESTATUS="${SLURM_SUBMIT_DIR:-$PWD}/.casestatus.md"

casestatus_log() {
    local f="$CASESTATUS" line tmp="$CASESTATUS.tmp.$$"
    line="- $(date '+%Y-%m-%d %H:%M')  $*"
    if [ ! -f "$f" ]; then
        printf -- '---\nstate: new\ntags: []\n---\n# %s\n\n## Notes\n\n## Log\n' \
            "$(basename "${SLURM_SUBMIT_DIR:-$PWD}")" > "$f" 2>/dev/null || return 0
    fi
    # at the end of the ## Log section, before the next heading (made if absent)
    awk -v line="$line" '
        inlog && /^##? / { print line; for (i = 0; i < nb; i++) print ""; if (!nb) print ""
                           nb = 0; inlog = 0; done = 1 }
        inlog && /^[ \t]*$/ { nb++; next }
        inlog { for (i = 0; i < nb; i++) print ""; nb = 0 }
        { print }
        $0 == "## Log" && !done { inlog = 1 }
        END { if (inlog) print line; else if (!done) { print ""; print "## Log"; print line } }
    ' "$f" > "$tmp" 2>/dev/null && mv -f "$tmp" "$f" || rm -f "$tmp"
    return 0
}


# REMOTE_TARGET (user@host, or a Host alias from ~/.ssh/config), REMOTE_PORT,
# REMOTE_DIR: set by `run post --remote NAME`. Empty REMOTE_TARGET = send
# nothing; empty REMOTE_PORT = whatever ssh would use (the alias's Port).
REMOTE_TARGET=${REMOTE_TARGET:-}
REMOTE_PORT=${REMOTE_PORT:-}
REMOTE_DIR=${REMOTE_DIR:-}
# A binary PLT counts as finished once it has not changed for this long
SEND_STABLE_SECS=${SEND_STABLE_SECS:-30}
# How often binary/ is checked for finished files while simPlt2Bin runs
SEND_POLL_SECS=${SEND_POLL_SECS:-60}

# -----------------------------------------------------------------------------
# Display job configuration
# -----------------------------------------------------------------------------

echo "=========================================="
echo "FlexFlow Postprocessing Job"
echo "=========================================="
echo "Problem:      $PROBLEM"
echo "Run Dir:      $RUN_DIR"
echo "Frequency:    $FREQ"
echo "Start Time:   $START_TIME (0 = beginning)"
echo "End Time:     $END_TIME"
echo "Processes:    $SLURM_NTASKS"
echo "CPUs/Task:    $SLURM_CPUS_PER_TASK"
if [ "$CONVERT_ONLY" = "1" ]; then
    echo "Mode:         convert-only (simPlt2Bin only, skipping simPlt)"
fi
if [ -n "$REMOTE_TARGET" ]; then
    echo "Send to:      ${REMOTE_TARGET}:${REMOTE_DIR}${REMOTE_PORT:+ (port ${REMOTE_PORT})}"
fi
echo "=========================================="
echo ""

# -----------------------------------------------------------------------------
# Validate executables
# -----------------------------------------------------------------------------

if [ "$CONVERT_ONLY" != "1" ] && [ ! -x "$SIMPLT" ]; then
    echo "Error: simPlt not found or not executable: $SIMPLT"
    exit 1
fi

if [ ! -x "$SIMPLT2BIN" ]; then
    echo "Error: simPlt2Bin not found or not executable: $SIMPLT2BIN"
    exit 1
fi

# Set OpenMP threads
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-$SLURM_CPUS_PER_TASK}

casestatus_log "post job ${SLURM_JOB_ID:-?} started: steps ${START_TIME}..${END_TIME} every ${FREQ}$([ "$CONVERT_ONLY" = 1 ] && echo ', convert only')${REMOTE_TARGET:+, sending to $REMOTE_TARGET}"
trap 'casestatus_log "post job ${SLURM_JOB_ID:-?} stopped: cancelled or out of walltime"; exit 143' TERM

# -----------------------------------------------------------------------------
# Step 1: Convert .out files to ASCII PLT files (simPlt)
# -----------------------------------------------------------------------------

if [ "$CONVERT_ONLY" = "1" ]; then
    echo "Step 1: Skipping simPlt (--convert mode)"
    echo ""
else
    echo "Step 1: Running simPlt to generate ASCII PLT files..."

    # Add -min only when processing from a non-zero start (e.g. after restart)
    MIN_ARG=""
    if [ "${START_TIME}" -gt 0 ] 2>/dev/null; then
        MIN_ARG="-min ${START_TIME}"
    fi

    echo "Command: $SIMPLT -n $SLURM_NTASKS -pb $PROBLEM -outFreq $FREQ ${MIN_ARG} -last $END_TIME"

    $SIMPLT -n $SLURM_NTASKS -pb $PROBLEM -outFreq $FREQ ${MIN_ARG} -last $END_TIME
    SIMPLT_EXIT=$?

    if [ $SIMPLT_EXIT -ne 0 ]; then
        # simPlt looks one outFreq step beyond the last processed timestep to check
        # for more files.  When --t2 is used the next step won't exist, causing a
        # non-zero exit even though all requested files were created successfully.
        # Treat this as success if the expected last plt file is present.
        EXPECTED_LAST="${PROBLEM}.${END_TIME}.plt"
        if [ -f "$EXPECTED_LAST" ]; then
            echo "Note: simPlt exited with code $SIMPLT_EXIT but $EXPECTED_LAST exists."
            echo "      Lookahead beyond END_TIME=$END_TIME is expected when using --t2."
        else
            echo "Error: simPlt failed with exit code $SIMPLT_EXIT"
            casestatus_log "post job ${SLURM_JOB_ID:-?} failed: simPlt exit $SIMPLT_EXIT"
            exit $SIMPLT_EXIT
        fi
    fi

    echo "✓ simPlt completed successfully"
    echo ""
fi

# -----------------------------------------------------------------------------
# Sending binary PLT files to a remote (run post --remote)
# -----------------------------------------------------------------------------
# A file is sent once it is finished: simPlt2Bin has not touched it for
# SEND_STABLE_SECS. Only files this job wrote (newer than START_MARK) for steps
# in [START_TIME, END_TIME] are sent. After simPlt2Bin exits, a final pass sends
# everything left, and resends any file that changed after it was sent.
# rsync writes to a temporary name and renames; without rsync on both ends,
# the file is streamed through ssh into a temporary name and renamed, which
# needs nothing on the remote but a shell (a BusyBox NAS has no scp server or
# rsync) -- either way the remote never holds a half-written file under its name.

BIN_DIR="binary"
SEND=0
SEND_LOG="post_sent_${SLURM_JOB_ID:-$$}.log"
START_MARK=".post_start_${SLURM_JOB_ID:-$$}"
declare -A SENT SEEN
UNSENT=()
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=20)
[ -n "$REMOTE_PORT" ] && SSH_OPTS+=(-p "$REMOTE_PORT")

# ssh and rsync both start in the remote home directory, so a leading ~/
# becomes a relative path (a quoted ~ would not be expanded)
remote_path() {
    case "$1" in
        "~")    echo "." ;;
        "~/"*)  echo "${1#\~/}" ;;
        *)      echo "$1" ;;
    esac
}

setup_send() {
    RDIR=$(remote_path "$REMOTE_DIR")
    if ! ssh "${SSH_OPTS[@]}" "$REMOTE_TARGET" "mkdir -p '$RDIR'"; then
        echo "Warning: could not reach ${REMOTE_TARGET} with key authentication."
        echo "         Binary PLT files will NOT be sent; send them later with:"
        echo "         case upload binary --t1 ${START_TIME} --t2 ${END_TIME}"
        return 1
    fi
    if command -v rsync >/dev/null 2>&1 \
            && ssh "${SSH_OPTS[@]}" "$REMOTE_TARGET" "command -v rsync" >/dev/null 2>&1; then
        USE_RSYNC=1
    else
        USE_RSYNC=0
    fi
    echo "Sending binary PLT files to ${REMOTE_TARGET}:${RDIR} ($( [ $USE_RSYNC = 1 ] && echo rsync || echo ssh ))"
    : > "$SEND_LOG"
    return 0
}

send_file() {
    local f="$1" name="${1##*/}"
    if [ "$USE_RSYNC" = 1 ]; then
        rsync -a --partial -e "ssh ${SSH_OPTS[*]}" "$f" "${REMOTE_TARGET}:${RDIR}/"
    else
        # a dropped connection ends the remote cat as if the file had ended,
        # so the size is checked before the rename
        local size part="${RDIR}/.${name}.part"
        size=$(stat -c %s "$f")
        ssh "${SSH_OPTS[@]}" "$REMOTE_TARGET" \
            "cat > '$part' && [ \$(wc -c < '$part') -eq $size ] && mv -f '$part' '${RDIR}/${name}'" < "$f"
    fi
}

# send_ready 0: send files that look finished; send_ready 1: send everything left
send_ready() {
    local final="$1" f name step sig now
    now=$(date +%s)
    [ "$final" = 1 ] && UNSENT=()
    for f in "$BIN_DIR"/"$PROBLEM".*.plt; do
        [ -f "$f" ] || continue
        name="${f##*/}"
        step="${name#"$PROBLEM".}"
        step="${step%.plt}"
        case "$step" in ''|*[!0-9]*) continue ;; esac
        [ "$step" -ge "$START_TIME" ] && [ "$step" -le "$END_TIME" ] || continue
        [ "$f" -nt "$START_MARK" ] || continue
        sig=$(stat -c '%s %Y' "$f")
        [ "${SENT[$f]:-}" = "$sig" ] && continue
        if [ "$final" != 1 ]; then
            # finished = same size and mtime as last check, and old enough
            if [ "${SEEN[$f]:-}" != "$sig" ]; then
                SEEN[$f]="$sig"
                continue
            fi
            [ $(( now - ${sig#* } )) -ge "$SEND_STABLE_SECS" ] || continue
        fi
        if send_file "$f"; then
            SENT[$f]="$sig"
            echo "$(date '+%F %T') sent ${name}" >> "$SEND_LOG"
        else
            echo "$(date '+%F %T') FAILED ${name}" >> "$SEND_LOG"
            [ "$final" = 1 ] && UNSENT+=("$name")
        fi
    done
}

if [ -n "$REMOTE_TARGET" ]; then
    setup_send && SEND=1
    echo ""
fi

# -----------------------------------------------------------------------------
# Step 2: Convert ASCII PLT to binary format (simPlt2Bin)
# -----------------------------------------------------------------------------

echo "Step 2: Running simPlt2Bin to convert to binary format..."

# Add -m only when processing from a non-zero start
MIN_ARG=""
if [ "${START_TIME}" -gt 0 ] 2>/dev/null; then
    MIN_ARG="-m ${START_TIME}"
fi

echo "Command: $SIMPLT2BIN -n $SLURM_NTASKS -w $RUN_DIR -f $FREQ -p $PROBLEM ${MIN_ARG} -l $END_TIME"

if [ "$SEND" = 1 ]; then
    # In the background, so finished files can be sent while the rest convert
    touch "$START_MARK"
    $SIMPLT2BIN -n $SLURM_NTASKS -w $RUN_DIR -f $FREQ -p $PROBLEM ${MIN_ARG} -l $END_TIME &
    SIMPLT2BIN_PID=$!
    while kill -0 "$SIMPLT2BIN_PID" 2>/dev/null; do
        waited=0
        while [ "$waited" -lt "$SEND_POLL_SECS" ] && kill -0 "$SIMPLT2BIN_PID" 2>/dev/null; do
            sleep 1
            waited=$((waited + 1))
        done
        send_ready 0
    done
    wait "$SIMPLT2BIN_PID"
    SIMPLT2BIN_EXIT=$?
else
    $SIMPLT2BIN -n $SLURM_NTASKS -w $RUN_DIR -f $FREQ -p $PROBLEM ${MIN_ARG} -l $END_TIME
    SIMPLT2BIN_EXIT=$?
fi

if [ $SIMPLT2BIN_EXIT -ne 0 ]; then
    echo "Error: simPlt2Bin failed with exit code $SIMPLT2BIN_EXIT"
    [ "$SEND" = 1 ] && echo "       Files sent before the failure are listed in $SEND_LOG"
    rm -f "$START_MARK"
    casestatus_log "post job ${SLURM_JOB_ID:-?} failed: simPlt2Bin exit $SIMPLT2BIN_EXIT"
    exit $SIMPLT2BIN_EXIT
fi

echo "✓ simPlt2Bin completed successfully"
echo ""

# -----------------------------------------------------------------------------
# Step 3: Send whatever is left (run post --remote)
# -----------------------------------------------------------------------------

if [ "$SEND" = 1 ]; then
    echo "Step 3: Sending the remaining binary PLT files..."
    send_ready 1
    n_sent=$(grep -c ' sent ' "$SEND_LOG")
    echo "✓ Sent ${n_sent} file(s) to ${REMOTE_TARGET}:${RDIR} (log: $SEND_LOG)"
    if [ ${#UNSENT[@]} -gt 0 ]; then
        echo "Warning: ${#UNSENT[@]} file(s) could not be sent: ${UNSENT[*]}"
        echo "         Send them later with: case upload binary --t1 ${START_TIME} --t2 ${END_TIME}"
    fi
    echo ""
fi
rm -f "$START_MARK"

# -----------------------------------------------------------------------------
# Job Complete
# -----------------------------------------------------------------------------

casestatus_log "post job ${SLURM_JOB_ID:-?} ended: binary PLT for steps ${START_TIME}..${END_TIME}${n_sent:+, $n_sent sent}"

echo "=========================================="
echo "Postprocessing completed successfully!"
echo "Binary PLT files are in: $BIN_DIR"
echo "=========================================="

exit 0
