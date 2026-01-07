#!/bin/bash
#SBATCH -J #jobname
#SBATCH -p medium 
#SBATCH -n 120 
#SBATCH --ntasks-per-node=40 # Necessary argument for medium partition
#SBATCH -t 72:00:00

# module load compiler/intel-mpi/mpi-2018.2.199 
# module load compiler/intel/2018.2.199
module load compiler/openmpi/4.0.2 

OUTDIR="RUN_1"

# Save the othd files in order
if [ -f ${OUTDIR}/riser.othd ]; then
        file_count=$(ls -p othd_files | grep -v / | wc -l);
        ((file_count++))
        mv "${OUTDIR}/riser.othd" "othd_files/riser${file_count}.othd"
        mv "${OUTDIR}/riser.oisd" "oisd_files/riser${file_count}.oisd"
        cp "riser.rcv" "rcv_files/riser${file_count}.rcv"
fi

#name of the executable
exe="/home/ritwikna/modalFlexFlow/bin/mpiSimflow"
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

#run the application
$exe -n $SLURM_NTASKS

