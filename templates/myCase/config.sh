#!/bin/bash
# FlexFlow Configuration File
# This file contains all configurable paths and settings for FlexFlow simulations
# Edit this file to match your HPC environment

# ============================================================================
# EXECUTABLE PATHS
# ============================================================================

# FlexFlow/Simflow binaries directory
# Default: /home/${USER}/modalFlexFlow/bin
export FLEXFLOW_BIN="${FLEXFLOW_BIN:-/home/${USER}/modalFlexFlow/bin}"

# Gmsh executable path
# Default: /home/${USER}/gmsh-4.4.1/bin/gmsh4
export GMSH_BIN="${GMSH_BIN:-/home/${USER}/gmsh-4.4.1/bin/gmsh4}"

# ============================================================================
# SIMULATION SETTINGS
# ============================================================================

# Problem/Case name (usually 'riser')
export PROBLEM="${PROBLEM:-riser}"

# Output directory for simulation results
export OUTDIR="${OUTDIR:-RUN_1}"

# Output frequency for PLT file generation
export OUTFREQ="${OUTFREQ:-50}"

# Last timestep to process
export LAST_TIME="${LAST_TIME:-4000}"

# ============================================================================
# SLURM DEFAULT SETTINGS (can be overridden by script)
# ============================================================================

# Default partition
export DEFAULT_PARTITION="shared"

# Default number of tasks for preprocessing
export DEFAULT_PRE_TASKS=8
export DEFAULT_PRE_CPUS_PER_TASK=4

# Default number of tasks for main simulation
export DEFAULT_MAIN_TASKS=36

# Default number of tasks for postprocessing
export DEFAULT_POST_TASKS=4
export DEFAULT_POST_CPUS_PER_TASK=4

# ============================================================================
# MODULE SETTINGS
# ============================================================================

# MPI module to load (OpenMPI or Intel MPI)
export MPI_MODULE="${MPI_MODULE:-compiler/openmpi/4.0.2}"

# Alternative MPI module (fallback)
export MPI_MODULE_ALT="${MPI_MODULE_ALT:-openmpi/4.0.2}"

# MATLAB module (for preprocessing)
export MATLAB_MODULE="${MATLAB_MODULE:-apps/matlab/R2022a}"

# ============================================================================
# OUTPUT DIRECTORIES
# ============================================================================

# Directories for storing output files
export OTHD_DIR="othd_files"
export OISD_DIR="oisd_files"
export RCV_DIR="rcv_files"
export PLT_DIR="plt_files"

# ============================================================================
# LOGGING
# ============================================================================

# Enable detailed logging (1=yes, 0=no)
export ENABLE_LOGGING="${ENABLE_LOGGING:-1}"

# Log directory
export LOG_DIR="${LOG_DIR:-logs}"

# ============================================================================
# EMAIL NOTIFICATIONS (optional)
# ============================================================================

# Email for SLURM notifications (set to your email)
# export SLURM_EMAIL="your.email@domain.com"

# ============================================================================
# ADVANCED SETTINGS
# ============================================================================

# Maximum walltime for different phases (HH:MM:SS)
export PRE_WALLTIME="24:00:00"
export MAIN_WALLTIME="72:00:00"
export POST_WALLTIME="24:00:00"

# Memory per CPU (if needed)
# export MEM_PER_CPU="4G"

# ============================================================================
# VALIDATION
# ============================================================================

# Check if critical paths exist (set to 0 to disable)
export VALIDATE_PATHS="${VALIDATE_PATHS:-1}"
