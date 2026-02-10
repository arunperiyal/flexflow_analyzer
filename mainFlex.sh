#!/bin/bash
#SBATCH -J mainflexflow_manager              # name of the job
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
# It also handles archiving of previous output files
#
# Usage:
#   sbatch mainFlex.sh
#
# For restart:
#   1. Ensure restart file exists: riser.rcv (copied from riser.TSID.rcv)
#   2. Submit job: sbatch mainFlex.sh
# =============================================================================

# Load required modules
# Uncomment and modify based on your cluster setup
# module load compiler/intel-mpi/mpi-2018.2.199
# module load compiler/intel/2018.2.199
# module load compiler/openmpi/4.0.2

# -----------------------------------------------------------------------------
# Parse simflow.config for default values
# -----------------------------------------------------------------------------

CONFIG_FILE="simflow.config"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: simflow.config not found in current directory"
    exit 1
fi

# Extract problem name from config
# Looks for: problem = "riser" or problem="riser"
PROBLEM=$(grep -oP '^\s*problem\s*=\s*"\K[^"]+' "$CONFIG_FILE")
if [ -z "$PROBLEM" ]; then
    echo "Error: Could not find 'problem' in simflow.config"
    exit 1
fi

# Extract run directory from config
# Looks for: dir = "RUN_1" or dir="RUN_1"
RUN_DIR=$(grep -oP '^\s*dir\s*=\s*"\K[^"]+' "$CONFIG_FILE")
if [ -z "$RUN_DIR" ]; then
    echo "Warning: Could not find 'dir' in simflow.config, using 'SIMFLOW_DATA'"
    RUN_DIR="SIMFLOW_DATA"
fi

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

# Check if this is a restart
if [ -f "${PROBLEM}.rcv" ]; then
    echo "✓ Restart file found: ${PROBLEM}.rcv"
    echo "  This will be a RESTART run"
else
    echo "ℹ No restart file found: ${PROBLEM}.rcv"
    echo "  This will be a NEW simulation"
fi
echo ""

# -----------------------------------------------------------------------------
# Archive previous output files (if any exist)
# -----------------------------------------------------------------------------

echo "Step 1: Archiving previous output files..."

# Create archive directories if they don't exist
mkdir -p othd_files
mkdir -p oisd_files
mkdir -p rcv_files

# Check if output files exist and archive them
ARCHIVED=0

if [ -f "${RUN_DIR}/${PROBLEM}.othd" ]; then
    # Count existing archived files
    file_count=$(ls -1 othd_files/ 2>/dev/null | grep -v / | wc -l)
    ((file_count++))

    mv "${RUN_DIR}/${PROBLEM}.othd" "othd_files/${PROBLEM}${file_count}.othd"
    echo "  ✓ Archived: ${PROBLEM}.othd → othd_files/${PROBLEM}${file_count}.othd"
    ARCHIVED=1
fi

if [ -f "${RUN_DIR}/${PROBLEM}.oisd" ]; then
    # Count existing archived files (should match othd count)
    file_count=$(ls -1 oisd_files/ 2>/dev/null | grep -v / | wc -l)
    ((file_count++))

    mv "${RUN_DIR}/${PROBLEM}.oisd" "oisd_files/${PROBLEM}${file_count}.oisd"
    echo "  ✓ Archived: ${PROBLEM}.oisd → oisd_files/${PROBLEM}${file_count}.oisd"
    ARCHIVED=1
fi

if [ -f "${PROBLEM}.rcv" ]; then
    # Count existing archived files
    file_count=$(ls -1 rcv_files/ 2>/dev/null | grep -v / | wc -l)
    ((file_count++))

    cp "${PROBLEM}.rcv" "rcv_files/${PROBLEM}${file_count}.rcv"
    echo "  ✓ Copied: ${PROBLEM}.rcv → rcv_files/${PROBLEM}${file_count}.rcv"
    ARCHIVED=1
fi

if [ $ARCHIVED -eq 0 ]; then
    echo "  No previous output files to archive"
fi

echo ""

# -----------------------------------------------------------------------------
# Set environment
# -----------------------------------------------------------------------------

# FlexFlow installation directory
if [ -z "$SIMFLOW_HOME" ]; then
    echo "Error: SIMFLOW_HOME environment variable not set"
    echo "Please set: export SIMFLOW_HOME=/path/to/flexflow"
    exit 1
fi

# MPI Simflow executable
MPISIMFLOW="${SIMFLOW_HOME}/bin/mpiSimflow"

# Verify executable exists
if [ ! -x "$MPISIMFLOW" ]; then
    echo "Error: mpiSimflow not found or not executable: $MPISIMFLOW"
    exit 1
fi

# Set OpenMP threads (if using hybrid MPI+OpenMP)
if [ -n "$SLURM_CPUS_PER_TASK" ]; then
    export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
fi

# -----------------------------------------------------------------------------
# Step 2: Run main simulation
# -----------------------------------------------------------------------------

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
    exit $SIMFLOW_EXIT
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
