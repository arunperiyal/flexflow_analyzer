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
        # for more files.  When --upto is used the next step won't exist, causing a
        # non-zero exit even though all requested files were created successfully.
        # Treat this as success if the expected last plt file is present.
        EXPECTED_LAST="${PROBLEM}.${END_TIME}.plt"
        if [ -f "$EXPECTED_LAST" ]; then
            echo "Note: simPlt exited with code $SIMPLT_EXIT but $EXPECTED_LAST exists."
            echo "      Lookahead beyond END_TIME=$END_TIME is expected when using --upto."
        else
            echo "Error: simPlt failed with exit code $SIMPLT_EXIT"
            exit $SIMPLT_EXIT
        fi
    fi

    echo "✓ simPlt completed successfully"
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

$SIMPLT2BIN -n $SLURM_NTASKS -w $RUN_DIR -f $FREQ -p $PROBLEM ${MIN_ARG} -l $END_TIME
SIMPLT2BIN_EXIT=$?

if [ $SIMPLT2BIN_EXIT -ne 0 ]; then
    echo "Error: simPlt2Bin failed with exit code $SIMPLT2BIN_EXIT"
    exit $SIMPLT2BIN_EXIT
fi

echo "✓ simPlt2Bin completed successfully"
echo ""

# -----------------------------------------------------------------------------
# Job Complete
# -----------------------------------------------------------------------------

echo "=========================================="
echo "Postprocessing completed successfully!"
echo "Binary PLT files are in: $RUN_DIR"
echo "=========================================="

exit 0
