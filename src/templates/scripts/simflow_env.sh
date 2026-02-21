#!/bin/bash
# =============================================================================
# FlexFlow Environment Configuration
# =============================================================================
# This file defines paths and environment settings for FlexFlow job scripts.
# All job scripts (preFlex.sh, mainFlex.sh, postFlex.sh) source this file.
#
# Edit this file to update paths without modifying individual job scripts.
#
# Usage (in job scripts):
#   source "$(dirname "$0")/simflow_env.sh"
# =============================================================================

# -----------------------------------------------------------------------------
# FlexFlow Installation
# -----------------------------------------------------------------------------

export SIMFLOW_HOME="/path/to/flexflow"

# Individual executables (derived from SIMFLOW_HOME by default)
export MPISIMFLOW="${SIMFLOW_HOME}/bin/mpiSimflow"
export SIMPLT="${SIMFLOW_HOME}/bin/simPlt"
export SIMPLT2BIN="${SIMFLOW_HOME}/bin/simPlt2Bin"
export SIMGMSHCNVT="${SIMFLOW_HOME}/bin/simGmshCnvt"

# -----------------------------------------------------------------------------
# Third-party Tools
# -----------------------------------------------------------------------------

# Gmsh mesh generator
export GMSH="gmsh"                   # Use 'which gmsh' to find the path

# -----------------------------------------------------------------------------
# OpenMP Settings
# -----------------------------------------------------------------------------

# Number of OpenMP threads per MPI process
# Leave commented to use SLURM_CPUS_PER_TASK automatically
# export OMP_NUM_THREADS=4

# -----------------------------------------------------------------------------
# Cluster Modules (optional)
# -----------------------------------------------------------------------------

# Uncomment if FlexFlow is available as a module
# module load flexflow

# Uncomment and modify based on your cluster setup
# module load compiler/openmpi/4.0.2
# module load compiler/intel-mpi/mpi-2018.2.199
# module load compiler/intel/2018.2.199
