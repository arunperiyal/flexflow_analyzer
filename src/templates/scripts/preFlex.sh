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
#   2. Mesh check - Stops the job if the mesh has triangles
#   3. simGmshCnvt - Converts Gmsh mesh to FlexFlow format
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

# CONVERT_ONLY: skip gmsh meshing and run only simGmshCnvt (env var, default: 0)
CONVERT_ONLY=${CONVERT_ONLY:-0}

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
if [ "$CONVERT_ONLY" = "1" ]; then
    echo "Mode:         convert-only (simGmshCnvt only, skipping gmsh)"
fi
echo "=========================================="
echo ""

# -----------------------------------------------------------------------------
# Validate executables
# -----------------------------------------------------------------------------

if [ "$CONVERT_ONLY" != "1" ] && ! command -v $GMSH &> /dev/null; then
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

if [ "$CONVERT_ONLY" = "1" ]; then
    echo "Step 1: Skipping gmsh (convert-only mode)"
    if [ ! -f "$MSH_FILE" ]; then
        echo "Error: convert-only requested but mesh file not found: $MSH_FILE"
        exit 1
    fi
    echo "✓ Using existing mesh: $MSH_FILE"
    echo ""
else
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
fi

# -----------------------------------------------------------------------------
# Step 2: Check the mesh for triangles (ASCII MSH 2.x / 4.x)
# -----------------------------------------------------------------------------

echo "Step 2: Checking mesh for triangles..."

MESH_CHECK=$(awk '
    BEGIN {
        split("2 9 20 21 22 23 24 25", t); for (i in t) tri[t[i]] = 1
        name[1] = "Line 2";       name[2] = "Triangle 3";      name[3] = "Quadrilateral 4"
        name[4] = "Tetrahedron 4"; name[5] = "Hexahedron 8";   name[6] = "Prism 6"
        name[7] = "Pyramid 5";    name[8] = "Line 3";          name[9] = "Triangle 6"
        name[10] = "Quadrilateral 9"; name[11] = "Tetrahedron 10"; name[15] = "Point"
    }
    /^\$MeshFormat/  { getline; ver = $1 + 0; if ($2 != 0) binary = 1; next }
    /^\$Elements/    { getline; inel = 1; seen = 1; next }
    /^\$EndElements/ { inel = 0; next }
    inel && !binary {
        if (ver < 4) { n[$2]++ }
        else { c = $4; n[$3] += c; for (i = 0; i < c; i++) getline }
    }
    END {
        if (binary) { print "binary .msh is not supported (set Mesh.Binary = 0)"; exit 2 }
        if (!seen)  { print "no $Elements section found"; exit 2 }
        for (e = 1; e <= 150; e++) if (e in n) {
            printf "  %-16s %d\n", (e in name ? name[e] : "type " e), n[e]
            if (e in tri) ntri += n[e]
        }
        printf "  Triangles total: %d\n", ntri
        exit (ntri > 0)
    }' "$MSH_FILE")
MESH_CHECK_EXIT=$?

echo "$MESH_CHECK"
echo "Mesh elements:" >> result.log
echo "$MESH_CHECK" >> result.log

if [ $MESH_CHECK_EXIT -eq 2 ]; then
    echo "Error: Could not read mesh file: $MSH_FILE"
    exit 1
elif [ $MESH_CHECK_EXIT -ne 0 ]; then
    echo "Error: Mesh contains triangles; fix $GEO_FILE (e.g. Recombine) and rerun"
    echo "       Skipping simGmshCnvt"
    exit 1
fi

echo "✓ No triangles in the mesh"
echo ""

# -----------------------------------------------------------------------------
# Step 3: Convert mesh to FlexFlow format
# -----------------------------------------------------------------------------

echo "Step 3: Running simGmshCnvt to convert mesh..."
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
# Step 4: Log mesh information
# -----------------------------------------------------------------------------

echo "Step 4: Logging mesh information..."

if [ -f "$MSH_FILE" ]; then
    echo "Number of Nodes in the mesh:" >> result.log
    awk '/\$Nodes/{ getline; print }' $MSH_FILE >> result.log
    echo "✓ Mesh info logged to result.log"
fi

echo ""

# -----------------------------------------------------------------------------
# Optional: Additional preprocessing steps
# -----------------------------------------------------------------------------

# Assign necessary periodic boundary conditions if necessary
# if [ ! -x "$SIMPBC" ]; then
#     echo "Error: simGmshCnvt not found or not executable: $SIMPBC"
#     exit 1
# fi

# SRF1="side1"
# SRF2="side"
# $SIMPBC -pbc1 $PROBLEM.${SRF1}.nbc -pbc2 $PROBLEM.${SRF2}.nbc
# SIMPBC_EXIT=$?

# Uncomment if you need to run MATLAB scripts
# echo "Step 5: Running MATLAB preprocessing..."
# matlab -batch writeBeamLineCrd

# -----------------------------------------------------------------------------
# Job Complete
# -----------------------------------------------------------------------------

echo "=========================================="
echo "Preprocessing completed successfully!"
echo "Ready to run main simulation"
echo "=========================================="

exit 0
