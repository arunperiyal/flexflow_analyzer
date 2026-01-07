#!/bin/bash
#SBATCH -J #jobname              # name of the job
#SBATCH -p shared           # name of the partition: available options "standard, standard-low, gpu, hm"
#SBATCH -n 8
#SBATCH --cpus-per-task=4
#SBATCH -t 24:00:00
#list of modules you want to use, for example

# module load compiler/openmpi/4.0.2 
module load apps/matlab/R2022a

# Creating the  mesh file
exe="/home/ritwikna/gmsh-4.4.1/bin/gmsh4"
$exe -3 riser.geo -o riser.msh

#name of the executable
exe="/home/ritwikna/modalFlexFlow/bin/simGmshCnvt"
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

#run the application
$exe -n $SLURM_NTASKS -msh riser.msh

echo "Number of Nodes in the mesh" >> result.log
awk '/\$Nodes/{ getline; print }' riser.msh >> result.log

matlab -batch writeBeamLineCrd
