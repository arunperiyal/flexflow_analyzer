#!/bin/bash
#SBATCH -J pre{CASE_NAME}               # name of the job
#SBATCH -p shared                       # partition: standard, standard-low, gpu, hm, shared
#SBATCH -n 30                           # number of processes/tasks
#SBATCH --cpus-per-task=1               # number of threads per process/task
#SBATCH -t 24:00:00                     # walltime in HH:MM:SS (Max: 72:00:00)

# =============================================================================
# FlexFlow Preprocessing Script Template
# =============================================================================
# This script runs preprocessing for FlexFlow simulations:
#   1. gmsh - Generates mesh from .geo file
#   2. simGmshCnvt - Converts Gmsh mesh to FlexFlow format
#
# The script auto-detects PROBLEM and GEO_FILE from simflow.config
#
# Usage:
#   sbatch preFlex.sh
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

# Look for .geo file (should match problem name)
GEO_FILE="${PROBLEM}.geo"
if [ ! -f "$GEO_FILE" ]; then
    # Try to find any .geo file
    GEO_FILE=$(find . -maxdepth 1 -name "*.geo" -type f | head -n 1)
    if [ -z "$GEO_FILE" ]; then
        echo "Error: No .geo file found"
        exit 1
    fi
    echo "Warning: ${PROBLEM}.geo not found, using: $GEO_FILE"
fi

# Mesh output file
MSH_FILE="${PROBLEM}.msh"

# -----------------------------------------------------------------------------
# Display job configuration
# -----------------------------------------------------------------------------

echo "=========================================="
echo "FlexFlow Preprocessing Job"
echo "=========================================="
echo "Problem:      $PROBLEM"
echo "Geo File:     $GEO_FILE"
echo "Mesh File:    $MSH_FILE"
echo "Processes:    $SLURM_NTASKS"
echo "CPUs/Task:    $SLURM_CPUS_PER_TASK"
echo "=========================================="
echo ""

# -----------------------------------------------------------------------------
# Validate executables
# -----------------------------------------------------------------------------

if ! command -v $GMSH &> /dev/null; then
    echo "Error: gmsh not found: $GMSH"
    exit 1
fi

if [ ! -x "$SIMGMSHCNVT" ]; then
    echo "Error: simGmshCnvt not found or not executable: $SIMGMSHCNVT"
    exit 1
fi

# Set OpenMP threads
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-$SLURM_CPUS_PER_TASK}

# -----------------------------------------------------------------------------
# Step 1: Generate mesh with Gmsh
# -----------------------------------------------------------------------------

echo "Step 1: Running gmsh to generate mesh..."
echo "Command: $GMSH -3 $GEO_FILE -o $MSH_FILE"

$GMSH -3 $GEO_FILE -o $MSH_FILE
GMSH_EXIT=$?

if [ $GMSH_EXIT -ne 0 ]; then
    echo "Error: gmsh failed with exit code $GMSH_EXIT"
    exit $GMSH_EXIT
fi

if [ ! -f "$MSH_FILE" ]; then
    echo "Error: Mesh file was not created: $MSH_FILE"
    exit 1
fi

echo "✓ Mesh generation completed successfully"
echo ""

# -----------------------------------------------------------------------------
# Step 2: Convert mesh to FlexFlow format
# -----------------------------------------------------------------------------

echo "Step 2: Running simGmshCnvt to convert mesh..."
echo "Command: $SIMGMSHCNVT -n $SLURM_NTASKS -msh $MSH_FILE"

$SIMGMSHCNVT -n $SLURM_NTASKS -msh $MSH_FILE
SIMGMSHCNVT_EXIT=$?

if [ $SIMGMSHCNVT_EXIT -ne 0 ]; then
    echo "Error: simGmshCnvt failed with exit code $SIMGMSHCNVT_EXIT"
    exit $SIMGMSHCNVT_EXIT
fi

echo "✓ Mesh conversion completed successfully"
echo ""

# -----------------------------------------------------------------------------
# Step 3: Log mesh information
# -----------------------------------------------------------------------------

echo "Step 3: Logging mesh information..."

if [ -f "$MSH_FILE" ]; then
    echo "Number of Nodes in the mesh:" >> result.log
    awk '/\$Nodes/{ getline; print }' $MSH_FILE >> result.log
    echo "✓ Mesh info logged to result.log"
fi

echo ""

# -----------------------------------------------------------------------------
# Optional: Additional preprocessing steps
# -----------------------------------------------------------------------------

# Uncomment if you need to run MATLAB scripts
# echo "Step 4: Running MATLAB preprocessing..."
# matlab -batch writeBeamLineCrd

# -----------------------------------------------------------------------------
# Job Complete
# -----------------------------------------------------------------------------

echo "=========================================="
echo "Preprocessing completed successfully!"
echo "Ready to run main simulation"
echo "=========================================="

exit 0
