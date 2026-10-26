#!/bin/bash
#SBATCH -J main{CASE_NAME}              # name of the job
#SBATCH -p medium                       # partition: standard, standard-low, gpu, hm, shared, medium
#SBATCH -n 120                          # number of processes/tasks
#SBATCH --ntasks-per-node=40            # tasks per node
#SBATCH -t 72:00:00                     # walltime in HH:MM:SS (Max: 72:00:00)

# =============================================================================
# FlexFlow Main Simulation Script Template
# =============================================================================
# This script runs the main FlexFlow simulation (mpiSimflow)
#
# The script auto-detects PROBLEM and RUN_DIR from simflow.config
# Before running, it archives any previous output files (.othd, .oisd, .rcv)
# into their respective archive directories (othd_files/, oisd_files/, rcv_files/)
#
# Usage:
#   sbatch mainFlex.sh
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

# Extract problem name from config
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

# -----------------------------------------------------------------------------
# Case notes: .casestatus.md (`case status`)
# -----------------------------------------------------------------------------
# The job adds its own lines to the ## Log section -- started, resumed from,
# ended -- and sets the state. Never fatal: a job does not fail over its notes.

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

# casestatus_state STATE: set the header's state, and log the change
casestatus_state() {
    local f="$CASESTATUS" old tmp="$CASESTATUS.tmp.$$"
    [ -f "$f" ] || casestatus_log "notes started by job ${SLURM_JOB_ID:-?}"
    old=$(awk '/^---[ \t]*$/ { if (++n == 2) exit; next }
               n == 1 && /^state:/ { sub(/^state:[ \t]*/, ""); sub(/[ \t]+#.*/, ""); print; exit }' "$f")
    [ "$old" = "$1" ] && return 0
    awk -v s="$1" '/^---[ \t]*$/ { n++ }
                   n == 1 && /^state:/ && !d { print "state: " s; d = 1; next } { print }' \
        "$f" > "$tmp" 2>/dev/null && mv -f "$tmp" "$f" || rm -f "$tmp"
    casestatus_log "state: ${old:--} -> $1"
}

# -----------------------------------------------------------------------------
# Display job configuration
# -----------------------------------------------------------------------------

echo "=========================================="
echo "FlexFlow Main Simulation Job"
echo "=========================================="
echo "Problem:      $PROBLEM"
echo "Run Dir:      $RUN_DIR"
echo "Processes:    $SLURM_NTASKS"
echo "CPUs/Task:    ${SLURM_CPUS_PER_TASK:-1}"
echo "Tasks/Node:   ${SLURM_NTASKS_PER_NODE:-N/A}"
echo "=========================================="
echo ""

# -----------------------------------------------------------------------------
# Archive previous output files (if any exist)
# -----------------------------------------------------------------------------

echo "Step 1: Archiving previous output files..."

# Create archive directories if they don't exist
mkdir -p othd_files
mkdir -p oisd_files
mkdir -p rcv_files

# Archive previous run's output if it exists
# .othd, .oisd, and .rcv are all archived together as a set
if [ -f "${RUN_DIR}/${PROBLEM}.othd" ]; then
    file_count=$(ls -p othd_files | grep -v / | wc -l)
    ((file_count++))

    mv "${RUN_DIR}/${PROBLEM}.othd" "othd_files/${PROBLEM}${file_count}.othd"
    mv "${RUN_DIR}/${PROBLEM}.oisd" "oisd_files/${PROBLEM}${file_count}.oisd"

    if [ -f "${PROBLEM}.rcv" ]; then
        cp "${PROBLEM}.rcv" "rcv_files/${PROBLEM}${file_count}.rcv"
        echo "  ✓ Archived run ${file_count}: .othd, .oisd, .rcv"
    else
        echo "  ✓ Archived run ${file_count}: .othd, .oisd (no .rcv found)"
    fi
else
    echo "  No previous output files to archive"
fi

echo ""

# -----------------------------------------------------------------------------
# Auto-restart configuration (managed by 'run main --dependency')
# Set to 1 by flexflow-manager when chaining dependent jobs; resets on fresh submit
# -----------------------------------------------------------------------------
APPLY_RESTART=0

if [ "$APPLY_RESTART" -eq 1 ]; then
    echo "Step 1b: Configuring auto-restart..."

    LATEST_OTHD=$(ls -t othd_files/*.othd 2>/dev/null | head -1)
    if [ -z "$LATEST_OTHD" ]; then
        echo "Error: APPLY_RESTART=1 but no .othd files found in othd_files/"
        exit 1
    fi

    LAST_TSID=$(grep "^tsId " "$LATEST_OTHD" | tail -1 | awk '{print $2}')
    if [ -z "$LAST_TSID" ]; then
        echo "Error: Could not read tsId from $LATEST_OTHD"
        exit 1
    fi

    echo "  Last tsId: $LAST_TSID (from $(basename "$LATEST_OTHD"))"

    grep -q "restartTsId" "$CONFIG_FILE" \
        && sed -i "s/^#*[[:space:]]*restartTsId[[:space:]]*=.*/restartTsId = $LAST_TSID/" "$CONFIG_FILE" \
        || echo "restartTsId = $LAST_TSID" >> "$CONFIG_FILE"
    grep -q "restartFlag" "$CONFIG_FILE" \
        && sed -i "s/^#*[[:space:]]*restartFlag[[:space:]]*=.*/restartFlag = 1/" "$CONFIG_FILE" \
        || echo "restartFlag = 1" >> "$CONFIG_FILE"

    echo "  ✓ simflow.config updated: restartTsId = $LAST_TSID, restartFlag = 1"
    echo ""
fi

# -----------------------------------------------------------------------------
# Validate executables
# -----------------------------------------------------------------------------

if [ ! -x "$MPISIMFLOW" ]; then
    echo "Error: mpiSimflow not found or not executable: $MPISIMFLOW"
    exit 1
fi

# Set OpenMP threads
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-$SLURM_CPUS_PER_TASK}

# -----------------------------------------------------------------------------
# Step 2: Run main simulation
# -----------------------------------------------------------------------------

# The restart as the run will see it (after any auto-restart above)
RESTART_FLAG=$(grep -oP '^\s*restartFlag\s*=\s*\K\d+' "$CONFIG_FILE" | head -1)
RESTART_TSID=$(grep -oP '^\s*restartTsId\s*=\s*\K\d+' "$CONFIG_FILE" | head -1)
MAX_STEPS=$(grep -oP 'maxTimeSteps\s*=\s*\K\d+' "${PROBLEM}.def" 2>/dev/null | head -1)
if [ "${RESTART_FLAG:-0}" != 0 ] && [ -n "$RESTART_TSID" ]; then
    casestatus_log "main job ${SLURM_JOB_ID:-?} started: resumed from ${RESTART_TSID} (np ${SLURM_NTASKS:-?})"
else
    casestatus_log "main job ${SLURM_JOB_ID:-?} started: from step 0 (np ${SLURM_NTASKS:-?})"
fi
casestatus_state running

# The step the run got to, from the .othd it writes
last_step() {
    grep '^tsId ' "${RUN_DIR}/${PROBLEM}.othd" 2>/dev/null | tail -1 | awk '{print $2}'
}

# scancel and the walltime limit send SIGTERM first
trap 'casestatus_log "main job ${SLURM_JOB_ID:-?} stopped at step $(last_step): cancelled or out of walltime"
      casestatus_state stopped; exit 143' TERM

echo "Step 2: Running main simulation..."
echo "Command: $MPISIMFLOW -n $SLURM_NTASKS"
echo ""
echo "=========================================="
echo "Simulation Output:"
echo "=========================================="

$MPISIMFLOW -n $SLURM_NTASKS

SIMFLOW_EXIT=$?

echo "=========================================="
echo ""

if [ $SIMFLOW_EXIT -ne 0 ]; then
    echo "Error: mpiSimflow failed with exit code $SIMFLOW_EXIT"
    casestatus_log "main job ${SLURM_JOB_ID:-?} failed at step $(last_step): mpiSimflow exit $SIMFLOW_EXIT"
    casestatus_state failed
    exit $SIMFLOW_EXIT
fi

STEP=$(last_step)
casestatus_log "main job ${SLURM_JOB_ID:-?} ended: exit 0 at step ${STEP:-?}${MAX_STEPS:+ of $MAX_STEPS}"
if [ -n "$STEP" ] && [ -n "$MAX_STEPS" ] && [ "$STEP" -ge "$MAX_STEPS" ]; then
    casestatus_state done
else
    casestatus_state stopped
fi

echo "✓ Simulation completed successfully"
echo ""

# -----------------------------------------------------------------------------
# Job Complete
# -----------------------------------------------------------------------------

echo "=========================================="
echo "Main simulation completed!"
echo "Output files in: $RUN_DIR"
echo "=========================================="

# Display next steps
echo ""
echo "Next steps:"
echo "  1. Check output files: ${PROBLEM}.othd, ${PROBLEM}.oisd"
echo "  2. Run postprocessing: run post"
echo ""

exit 0
