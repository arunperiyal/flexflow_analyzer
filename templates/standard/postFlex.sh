#!/bin/bash
#SBATCH -J __JOBNAME___post
#SBATCH -p shared
#SBATCH -n 4
#SBATCH --cpus-per-task=4
#SBATCH -t 24:00:00
#SBATCH --output=slurm-post-%j.out
#SBATCH --error=slurm-post-%j.err
##SBATCH --mail-type=END,FAIL
##SBATCH --mail-user=your.email@domain.com

# ==============================================================================
# FlexFlow Post-Processing Script
# 
# This script performs post-processing tasks:
#   1. Extract PLT files from simulation output
#   2. Convert PLT files from ASCII to binary format
#
# Usage: sbatch postFlex.sh
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
    mkdir -p "${PLT_DIR}"
    
    # Set OpenMP threads
    set_omp_threads
    
    # ----------------------------------------------------------------------
    # Step 1: Validate configuration
    # ----------------------------------------------------------------------
    log_info "=========================================="
    log_info "Step 1: Configuration"
    log_info "=========================================="
    
    log_info "Problem: ${PROBLEM}"
    log_info "Output directory: ${OUTDIR}"
    log_info "Output frequency: ${OUTFREQ}"
    log_info "Last timestep: ${LAST_TIME}"
    
    # Check if output files exist
    if [ ! -f "${OUTDIR}/${PROBLEM}.out" ]; then
        log_error "Output file not found: ${OUTDIR}/${PROBLEM}.out"
        log_error "Make sure the simulation has completed successfully"
        exit 1
    fi
    
    # ----------------------------------------------------------------------
    # Step 2: Extract PLT files from output
    # ----------------------------------------------------------------------
    log_info "=========================================="
    log_info "Step 2: Extracting PLT files"
    log_info "=========================================="
    
    local plt_extractor="${FLEXFLOW_BIN}/simPlt"
    check_executable "${plt_extractor}" "simPlt" || exit 1
    
    # Fixed: Changed ${RISER} to ${PROBLEM}
    run_cmd "PLT extraction" \
        "${plt_extractor}" -n ${SLURM_NTASKS} \
                          -pb ${PROBLEM} \
                          -outFreq ${OUTFREQ} \
                          -last ${LAST_TIME}
    
    # Check if PLT files were created
    local plt_count=$(count_files "${OUTDIR}" "*.plt")
    if [ ${plt_count} -gt 0 ]; then
        log_success "Extracted ${plt_count} PLT files"
    else
        log_error "No PLT files were extracted"
        exit 1
    fi
    
    # ----------------------------------------------------------------------
    # Step 3: Convert PLT files to binary format
    # ----------------------------------------------------------------------
    log_info "=========================================="
    log_info "Step 3: Converting PLT files to binary"
    log_info "=========================================="
    
    local plt_converter="${FLEXFLOW_BIN}/simPlt2Bin"
    check_executable "${plt_converter}" "simPlt2Bin" || exit 1
    
    # Fixed: Changed ${OURFREQ} to ${OUTFREQ}
    run_cmd "PLT conversion" \
        "${plt_converter}" -n ${SLURM_NTASKS} \
                          -w ${OUTDIR} \
                          -f ${OUTFREQ} \
                          -p ${PROBLEM} \
                          -l ${LAST_TIME}
    
    # ----------------------------------------------------------------------
    # Step 4: Move PLT files to archive directory
    # ----------------------------------------------------------------------
    log_info "=========================================="
    log_info "Step 4: Archiving PLT files"
    log_info "=========================================="
    
    if [ -d "${OUTDIR}" ] && [ ${plt_count} -gt 0 ]; then
        log_info "Moving PLT files to ${PLT_DIR}..."
        mv "${OUTDIR}"/*.plt "${PLT_DIR}/" 2>/dev/null || true
        
        local archived_count=$(count_files "${PLT_DIR}" "*.plt")
        log_success "Archived ${archived_count} PLT files to ${PLT_DIR}"
    fi
    
    # ----------------------------------------------------------------------
    # Step 5: Generate summary
    # ----------------------------------------------------------------------
    log_info "=========================================="
    log_info "Step 5: Summary"
    log_info "=========================================="
    
    # Count output files
    local othd_count=$(count_files "${OTHD_DIR}" "*.othd")
    local oisd_count=$(count_files "${OISD_DIR}" "*.oisd")
    local plt_count=$(count_files "${PLT_DIR}" "*.plt")
    
    log_info "Output file summary:"
    log_info "  OTHD files: ${othd_count}"
    log_info "  OISD files: ${oisd_count}"
    log_info "  PLT files:  ${plt_count}"
    
    # Print summary
    print_job_summary
    
    log_success "Post-processing completed successfully!"
    log_info "PLT files are in: ${PLT_DIR}"
    log_info "Use FlexFlow to analyze: ff check ${OTHD_DIR}/*.othd"
}

# Run main function
main "$@"
