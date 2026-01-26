#!/bin/bash
#SBATCH -J __JOBNAME___main
#SBATCH -p medium
#SBATCH -n 36
#SBATCH --ntasks-per-node=40
#SBATCH -t 72:00:00
#SBATCH --output=slurm-main-%j.out
#SBATCH --error=slurm-main-%j.err
##SBATCH --mail-type=END,FAIL
##SBATCH --mail-user=your.email@domain.com

# ==============================================================================
# FlexFlow Main Simulation Script
# 
# This script performs the main FlexFlow simulation:
#   1. Save previous output files (if restart)
#   2. Run mpiSimflow with specified number of tasks
#   3. Archive output files with sequential numbering
#
# Usage: sbatch mainFlex.sh
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
    log_info "Loading MPI module..."
    load_module_safe "${MPI_MODULE}" "${MPI_MODULE_ALT}" || exit 1
    
    # Create output directories
    create_output_dirs
    
    # Set OpenMP threads
    set_omp_threads
    
    # ----------------------------------------------------------------------
    # Step 1: Save previous output files (if any)
    # ----------------------------------------------------------------------
    log_info "=========================================="
    log_info "Step 1: Checking for previous output files"
    log_info "=========================================="
    
    save_output_files "${PROBLEM}" "${OUTDIR}"
    
    # ----------------------------------------------------------------------
    # Step 2: Validate input files
    # ----------------------------------------------------------------------
    log_info "=========================================="
    log_info "Step 2: Validating input files"
    log_info "=========================================="
    
    check_file "${PROBLEM}.def" "Definition file" || exit 1
    check_file "simflow.config" "Config file" || exit 1
    
    # ----------------------------------------------------------------------
    # Step 3: Run main simulation
    # ----------------------------------------------------------------------
    log_info "=========================================="
    log_info "Step 3: Running FlexFlow simulation"
    log_info "=========================================="
    
    local sim_exe="${FLEXFLOW_BIN}/mpiSimflow"
    check_executable "${sim_exe}" "mpiSimflow" || exit 1
    
    log_info "Problem: ${PROBLEM}"
    log_info "Output directory: ${OUTDIR}"
    log_info "Number of MPI tasks: ${SLURM_NTASKS}"
    
    # Run simulation
    run_cmd "FlexFlow simulation" \
        "${sim_exe}" -n ${SLURM_NTASKS}
    
    # ----------------------------------------------------------------------
    # Step 4: Verify output files
    # ----------------------------------------------------------------------
    log_info "=========================================="
    log_info "Step 4: Verifying output files"
    log_info "=========================================="
    
    if [ -f "${OUTDIR}/${PROBLEM}.othd" ]; then
        local file_size=$(du -h "${OUTDIR}/${PROBLEM}.othd" | cut -f1)
        log_success "OTHD file created: ${file_size}"
    else
        log_warning "OTHD file not found in ${OUTDIR}"
    fi
    
    if [ -f "${OUTDIR}/${PROBLEM}.oisd" ]; then
        local file_size=$(du -h "${OUTDIR}/${PROBLEM}.oisd" | cut -f1)
        log_success "OISD file created: ${file_size}"
    else
        log_warning "OISD file not found in ${OUTDIR}"
    fi
    
    # Print summary
    print_job_summary
    
    log_success "Simulation completed successfully!"
    log_info "Output files are in: ${OUTDIR}"
    log_info "Run postFlex.sh to extract PLT files"
}

# Run main function
main "$@"
