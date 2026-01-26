#!/bin/bash
#SBATCH -J __JOBNAME___pre
#SBATCH -p shared
#SBATCH -n 8
#SBATCH --cpus-per-task=4
#SBATCH -t 24:00:00
#SBATCH --output=slurm-pre-%j.out
#SBATCH --error=slurm-pre-%j.err
##SBATCH --mail-type=END,FAIL
##SBATCH --mail-user=your.email@domain.com

# ==============================================================================
# FlexFlow Pre-Processing Script
# 
# This script performs the following tasks:
#   1. Generate mesh file using Gmsh
#   2. Convert mesh to FlexFlow format
#   3. Run MATLAB preprocessing (if needed)
#
# Usage: sbatch preFlex.sh
# ==============================================================================

# Load configuration and common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"
source "${SCRIPT_DIR}/common.sh"

# Set error handling
set_error_handling

# Initialize logging
init_logging

# Register cleanup handler
register_cleanup

# ==============================================================================
# MAIN SCRIPT
# ==============================================================================

main() {
    # Print job information
    print_job_info
    
    # Validate environment
    validate_environment || exit 1
    
    # Load required modules
    log_info "Loading required modules..."
    load_module_safe "${MATLAB_MODULE}" || log_warning "MATLAB module not loaded, continuing..."
    
    # Create output directories
    create_output_dirs
    
    # Set OpenMP threads
    set_omp_threads
    
    # ----------------------------------------------------------------------
    # Step 1: Generate mesh file using Gmsh
    # ----------------------------------------------------------------------
    log_info "=========================================="
    log_info "Step 1: Generating mesh with Gmsh"
    log_info "=========================================="
    
    check_file "${PROBLEM}.geo" "Geometry file" || exit 1
    check_executable "${GMSH_BIN}" "Gmsh" || exit 1
    
    run_cmd "Mesh generation" \
        "${GMSH_BIN}" -3 "${PROBLEM}.geo" -o "${PROBLEM}.msh"
    
    check_file "${PROBLEM}.msh" "Mesh file" || exit 1
    
    # ----------------------------------------------------------------------
    # Step 2: Convert mesh to FlexFlow format
    # ----------------------------------------------------------------------
    log_info "=========================================="
    log_info "Step 2: Converting mesh to FlexFlow format"
    log_info "=========================================="
    
    local gmsh_converter="${FLEXFLOW_BIN}/simGmshCnvt"
    check_executable "${gmsh_converter}" "Gmsh converter" || exit 1
    
    run_cmd "Mesh conversion" \
        "${gmsh_converter}" -n ${SLURM_NTASKS} -msh "${PROBLEM}.msh"
    
    # ----------------------------------------------------------------------
    # Step 3: Log mesh information
    # ----------------------------------------------------------------------
    log_info "=========================================="
    log_info "Step 3: Extracting mesh information"
    log_info "=========================================="
    
    if [ -f "${PROBLEM}.msh" ]; then
        local num_nodes=$(awk '/\$Nodes/{ getline; print }' "${PROBLEM}.msh")
        log_success "Number of nodes in mesh: ${num_nodes}"
        echo "Number of Nodes in the mesh: ${num_nodes}" >> result.log
    fi
    
    # ----------------------------------------------------------------------
    # Step 4: Run MATLAB preprocessing (optional)
    # ----------------------------------------------------------------------
    log_info "=========================================="
    log_info "Step 4: Running MATLAB preprocessing"
    log_info "=========================================="
    
    if [ -f "writeBeamLineCrd.m" ]; then
        if command -v matlab &> /dev/null; then
            run_cmd "MATLAB preprocessing" \
                matlab -batch writeBeamLineCrd
        else
            log_warning "MATLAB not available, skipping preprocessing"
        fi
    else
        log_info "No MATLAB script found, skipping preprocessing"
    fi
    
    # Print summary
    print_job_summary
    
    log_success "Pre-processing completed successfully!"
}

# Run main function
main "$@"
