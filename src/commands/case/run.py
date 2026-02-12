"""
Case run subcommand - Submit and monitor SLURM jobs for FlexFlow simulations
"""

import os
import sys
import time
import subprocess
import re
from pathlib import Path


class CaseRunCommand:
    """Handle case run operations"""
    
    def __init__(self, case_dir, no_monitor=False, clean=False, from_step=None, dry_run=False):
        self.case_dir = Path(case_dir).resolve()
        self.no_monitor = no_monitor
        self.clean = clean
        self.from_step = from_step
        self.dry_run = dry_run
        
        # Will be populated from config files
        self.problem_name = None
        self.output_dir = None
        self.max_timesteps = None
        self.out_freq = None
        self.nsg = None
        
    def execute(self):
        """Main execution flow"""
        print(f"[FlexFlow] Starting case: {self.case_dir.name}")
        
        # Step 1: Check SLURM availability
        if not self.check_slurm_available():
            print("Error: SLURM commands not available")
            return False
        
        # Step 2: Verify case directory structure
        if not self.verify_case_structure():
            return False
        
        # Step 3: Parse configuration files
        if not self.parse_configs():
            return False
        
        # Step 4: Check if case is already running
        if self.is_case_running():
            print(f"Error: Case '{self.case_dir.name}' is already running!")
            print("Use 'squeue' to check job status.")
            return False
        
        # Step 5: Determine if this is first run or restart
        is_first_run = self.is_first_run()
        
        if self.clean:
            print("[FlexFlow] Clean start requested - removing existing OTHD files")
            is_first_run = True
            if not self.dry_run:
                self.clean_output_dir()
        
        # Step 6: Setup restart configuration
        if not is_first_run:
            last_tsid = self.get_last_timestep()
            if last_tsid is None:
                print("Error: Cannot determine last timestep from OTHD file")
                return False
            
            if self.from_step:
                last_tsid = self.from_step
            
            print(f"[FlexFlow] Restart from timestep: {last_tsid}")
            if not self.dry_run:
                self.update_restart_config(last_tsid)
                self.log_restart(last_tsid)
        else:
            print("[FlexFlow] First run - starting from timestep 0")
            if not self.dry_run:
                self.ensure_restart_disabled()
                self.log_restart(0, first_run=True)
        
        # Step 7: Ensure required directories exist
        if not self.dry_run:
            self.ensure_directories()
        
        # Step 8: Submit jobs
        job_ids = {}
        
        # Submit preFlex only on first run
        if is_first_run:
            print("[FlexFlow] Submitting preFlex.sh (mesh generation)...")
            if not self.dry_run:
                job_ids['preFlex'] = self.submit_job('preFlex.sh')
                print(f"[FlexFlow] preFlex job submitted: {job_ids['preFlex']}")
            else:
                print("[DRY-RUN] Would submit: preFlex.sh")
        
        # Submit mainFlex with dependency on preFlex if applicable
        print("[FlexFlow] Submitting mainFlex.sh (main simulation)...")
        if not self.dry_run:
            dependency = job_ids.get('preFlex')
            job_ids['mainFlex'] = self.submit_job('mainFlex.sh', dependency=dependency)
            print(f"[FlexFlow] mainFlex job submitted: {job_ids['mainFlex']}")
        else:
            print("[DRY-RUN] Would submit: mainFlex.sh")
            if is_first_run:
                print("[DRY-RUN]   with dependency on preFlex")
        
        if self.dry_run:
            print("\n[DRY-RUN] Summary:")
            print(f"  Case: {self.case_dir.name}")
            print(f"  Problem: {self.problem_name}")
            print(f"  Output: {self.output_dir}")
            print(f"  Max steps: {self.max_timesteps}")
            print(f"  First run: {is_first_run}")
            return True
        
        # Step 9: Monitor if requested
        if not self.no_monitor:
            print("\n[FlexFlow] Monitoring job progress...")
            print("Press Ctrl+C to stop monitoring (jobs will continue running)")
            try:
                self.monitor_jobs(job_ids)
            except KeyboardInterrupt:
                print("\n[FlexFlow] Monitoring stopped (jobs still running)")
        else:
            print("\n[FlexFlow] Jobs submitted. Use 'squeue' to monitor progress.")
            print(f"[FlexFlow] Run 'flexflow case run {self.case_dir.name}' again after mainFlex completes.")
        
        return True
    
    def check_slurm_available(self):
        """Check if SLURM commands are available"""
        required_cmds = ['sbatch', 'squeue', 'scancel']
        for cmd in required_cmds:
            if subprocess.run(['which', cmd], capture_output=True).returncode != 0:
                print(f"Error: SLURM command '{cmd}' not found")
                return False
        return True
    
    def verify_case_structure(self):
        """Verify case directory has required files"""
        if not self.case_dir.exists():
            print(f"Error: Case directory not found: {self.case_dir}")
            return False
        
        required_files = ['simflow.config', 'preFlex.sh', 'mainFlex.sh', 'postFlex.sh']
        missing_files = []
        
        for fname in required_files:
            if not (self.case_dir / fname).exists():
                missing_files.append(fname)
        
        if missing_files:
            print(f"Error: Missing required files: {', '.join(missing_files)}")
            return False
        
        # Find .def file
        def_files = list(self.case_dir.glob('*.def'))
        if not def_files:
            print("Error: No .def file found in case directory")
            return False
        
        return True
    
    def parse_configs(self):
        """Parse simflow.config and .def files"""
        from src.core.simflow_config import SimflowConfig
        cfg = SimflowConfig.find(self.case_dir)

        self.problem_name = cfg.problem
        run_dir = cfg.run_dir(self.case_dir)
        self.output_dir = run_dir.name if run_dir else None
        self.out_freq = cfg.out_freq
        self.nsg = cfg.nsg

        if not self.problem_name or not self.output_dir:
            print("Error: Could not parse problem name or output directory from simflow.config")
            return False
        
        # Parse .def file for maxTimeSteps
        from src.core.def_config import DefConfig
        def_cfg = DefConfig.find(self.case_dir, self.problem_name)
        self.max_timesteps = def_cfg.max_time_steps

        if not self.max_timesteps:
            print("Error: Could not find maxTimeSteps in .def file")
            return False
        
        print(f"[FlexFlow] Configuration:")
        print(f"  Problem: {self.problem_name}")
        print(f"  Output dir: {self.output_dir}")
        print(f"  Max timesteps: {self.max_timesteps}")
        print(f"  Output frequency: {self.out_freq}")
        
        return True
    
    def is_case_running(self):
        """Check if this case is already running"""
        case_name = self.case_dir.name
        username = os.environ.get('USER', '')
        
        # Method 1: Check SLURM queue
        try:
            result = subprocess.run(
                ['squeue', '-u', username, '-h', '-o', '%j'],
                capture_output=True, text=True, check=True
            )
            job_names = result.stdout.strip().split('\n')
            
            # Check for job names containing the case name
            for job_name in job_names:
                if case_name in job_name and ('main_' in job_name or 'pre_' in job_name):
                    return True
        except subprocess.CalledProcessError:
            pass
        
        # Method 2: Check for active process
        try:
            result = subprocess.run(
                ['ps', 'aux'],
                capture_output=True, text=True
            )
            if 'mpiSimflow' in result.stdout and str(self.case_dir) in result.stdout:
                return True
        except:
            pass
        
        return False
    
    def is_first_run(self):
        """Check if this is the first run"""
        othd_file = self.case_dir / self.output_dir / f'{self.problem_name}.othd'
        restart_log = self.case_dir / 'restart.log'
        
        # If OTHD file doesn't exist or restart.log is empty, it's first run
        if not othd_file.exists():
            return True
        
        if not restart_log.exists() or restart_log.stat().st_size == 0:
            return True
        
        return False
    
    def get_last_timestep(self):
        """Get last completed timestep from OTHD file"""
        othd_file = self.case_dir / self.output_dir / f'{self.problem_name}.othd'
        
        if not othd_file.exists():
            return None
        
        try:
            result = subprocess.run(
                ['grep', '^tsId', str(othd_file)],
                capture_output=True, text=True
            )
            lines = result.stdout.strip().split('\n')
            if lines and lines[0]:
                last_line = lines[-1]
                match = re.search(r'tsId\s+(\d+)', last_line)
                if match:
                    return int(match.group(1))
        except:
            pass
        
        return None
    
    def clean_output_dir(self):
        """Clean output directory for fresh start"""
        output_path = self.case_dir / self.output_dir
        if output_path.exists():
            import shutil
            for item in output_path.iterdir():
                if item.is_file():
                    item.unlink()
    
    def update_restart_config(self, last_tsid):
        """Update simflow.config to enable restart from last_tsid"""
        config_file = self.case_dir / 'simflow.config'
        
        try:
            with open(config_file, 'r') as f:
                lines = f.readlines()
            
            with open(config_file, 'w') as f:
                for line in lines:
                    # Uncomment and set restartTsId
                    if 'restartTsId' in line:
                        f.write(f'restartTsId = {last_tsid}\n')
                    # Uncomment and enable restartFlag
                    elif 'restartFlag' in line:
                        f.write('restartFlag = 1\n')
                    else:
                        f.write(line)
        except Exception as e:
            print(f"Error updating restart config: {e}")
            raise
    
    def ensure_restart_disabled(self):
        """Ensure restart is commented out for first run"""
        config_file = self.case_dir / 'simflow.config'
        
        try:
            with open(config_file, 'r') as f:
                lines = f.readlines()
            
            with open(config_file, 'w') as f:
                for line in lines:
                    # Comment out restartTsId and restartFlag
                    if line.strip().startswith('restartTsId'):
                        f.write(f'#{line.lstrip("#")}')
                    elif line.strip().startswith('restartFlag'):
                        f.write(f'#{line.lstrip("#")}')
                    else:
                        f.write(line)
        except Exception as e:
            print(f"Error disabling restart: {e}")
            raise
    
    def log_restart(self, tsid, first_run=False):
        """Log restart information to restart.log"""
        restart_log = self.case_dir / 'restart.log'
        
        # Create header if file doesn't exist
        if not restart_log.exists():
            with open(restart_log, 'w') as f:
                f.write('Timestamp,Run,StartTsId,EndTsId,Duration,JobID,Status\n')
        
        # For first run, just initialize
        if first_run:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            with open(restart_log, 'a') as f:
                f.write(f'{timestamp},1,0,-,-,-,SUBMITTED\n')
    
    def ensure_directories(self):
        """Ensure required directories exist"""
        dirs = ['othd_files', 'oisd_files', 'rcv_files', 'binary', self.output_dir]
        
        for dir_name in dirs:
            dir_path = self.case_dir / dir_name
            dir_path.mkdir(exist_ok=True)
    
    def submit_job(self, script_name, dependency=None):
        """Submit SLURM job and return job ID"""
        script_path = self.case_dir / script_name
        
        cmd = ['sbatch']
        if dependency:
            cmd.extend(['--dependency', f'afterok:{dependency}'])
        cmd.append(str(script_path))
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=str(self.case_dir)
            )
            
            # Extract job ID from output: "Submitted batch job 12345"
            match = re.search(r'Submitted batch job (\d+)', result.stdout)
            if match:
                return match.group(1)
        except subprocess.CalledProcessError as e:
            print(f"Error submitting {script_name}: {e.stderr}")
            raise
        
        return None
    
    def monitor_jobs(self, job_ids):
        """Monitor job progress"""
        main_job = job_ids.get('mainFlex')
        if not main_job:
            return
        
        print(f"[FlexFlow] Monitoring job: {main_job}")
        
        while True:
            # Check job status
            status = self.get_job_status(main_job)
            
            if status == 'RUNNING':
                # Get current progress
                last_tsid = self.get_last_timestep()
                if last_tsid is not None:
                    progress = (last_tsid / self.max_timesteps) * 100
                    print(f"[FlexFlow] Progress: {last_tsid}/{self.max_timesteps} ({progress:.1f}%)")
                else:
                    print(f"[FlexFlow] Job running, waiting for OTHD file...")
            
            elif status == 'PENDING':
                print(f"[FlexFlow] Job pending in queue...")
            
            elif status == 'COMPLETED':
                print(f"[FlexFlow] Job completed!")
                
                # Check if simulation is complete
                last_tsid = self.get_last_timestep()
                if last_tsid >= self.max_timesteps:
                    print(f"[FlexFlow] Simulation complete! Submitting postFlex...")
                    self.submit_job('postFlex.sh')
                    break
                else:
                    print(f"[FlexFlow] Simulation at step {last_tsid}, restarting...")
                    # Restart will be handled by running the command again
                    break
            
            elif status == 'FAILED':
                print(f"[FlexFlow] Job failed! Check SLURM logs.")
                break
            
            elif status is None:
                print(f"[FlexFlow] Job not found in queue (may have completed)")
                break
            
            time.sleep(30)
    
    def get_job_status(self, job_id):
        """Get SLURM job status"""
        try:
            result = subprocess.run(
                ['squeue', '-j', job_id, '-h', '-o', '%T'],
                capture_output=True,
                text=True,
                check=True
            )
            
            status = result.stdout.strip()
            return status if status else None
        except subprocess.CalledProcessError:
            return None


def execute_case_run(args):
    """Execute case run command"""
    # Handle help flag
    if hasattr(args, 'help') and args.help:
        show_run_help()
        return
    
    # Handle examples flag
    if hasattr(args, 'examples') and args.examples:
        show_run_examples()
        return
    
    if not hasattr(args, 'case') or not args.case:
        print("Error: Case directory is required")
        print("\nUsage: flexflow case run <case_dir> [options]")
        print("Use 'flexflow case run --help' for more information")
        return
    
    runner = CaseRunCommand(
        case_dir=args.case,
        no_monitor=args.no_monitor,
        clean=args.clean,
        from_step=args.from_step,
        dry_run=args.dry_run
    )
    
    try:
        success = runner.execute()
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def show_run_help():
    """Show help for case run command"""
    from rich.console import Console
    from rich.table import Table
    from rich import box
    
    console = Console()
    console.print()
    console.print("[bold cyan]FlexFlow Case Run Command[/bold cyan]")
    console.print()
    console.print("Submit and monitor SLURM jobs for FlexFlow simulations.")
    console.print()
    console.print("[bold]USAGE:[/bold]")
    console.print("    flexflow case run <case_dir> [options]")
    console.print()
    
    # Options table
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
    table.add_column("Option", style="cyan")
    table.add_column("Description", style="white")
    
    table.add_row("--no-monitor", "Submit jobs without monitoring progress")
    table.add_row("--clean", "Clean start (remove existing OTHD files)")
    table.add_row("--from-step N", "Restart from specific timestep")
    table.add_row("--dry-run", "Preview actions without submitting jobs")
    table.add_row("-v, --verbose", "Enable verbose output")
    table.add_row("-h, --help", "Show this help message")
    table.add_row("--examples", "Show usage examples")
    
    console.print("[bold]OPTIONS:[/bold]")
    console.print(table)
    console.print()
    console.print("[bold]DESCRIPTION:[/bold]")
    console.print("  Submits SLURM jobs in the correct order:")
    console.print("    1. preFlex.sh  - Mesh generation (first run only)")
    console.print("    2. mainFlex.sh - Main simulation")
    console.print("    3. postFlex.sh - Post-processing (after completion)")
    console.print()
    console.print("  Automatically handles:")
    console.print("    • First run vs. restart detection")
    console.print("    • Restart configuration from OTHD files")
    console.print("    • Job dependencies and monitoring")
    console.print()


def show_run_examples():
    """Show examples for case run command"""
    from rich.console import Console
    
    console = Console()
    console.print()
    console.print("[bold cyan]Case Run Examples[/bold cyan]")
    console.print()
    console.print("[bold]Basic usage:[/bold]")
    console.print("    flexflow case run CS4SG1U1")
    console.print("    → Submit jobs and monitor progress")
    console.print()
    console.print("[bold]Submit without monitoring:[/bold]")
    console.print("    flexflow case run CS4SG1U1 --no-monitor")
    console.print("    → Submit jobs and exit immediately")
    console.print()
    console.print("[bold]Clean restart:[/bold]")
    console.print("    flexflow case run CS4SG1U1 --clean")
    console.print("    → Remove existing output and start fresh")
    console.print()
    console.print("[bold]Resume from specific step:[/bold]")
    console.print("    flexflow case run CS4SG1U1 --from-step 5000")
    console.print("    → Restart simulation from timestep 5000")
    console.print()
    console.print("[bold]Preview without submitting:[/bold]")
    console.print("    flexflow case run CS4SG1U1 --dry-run")
    console.print("    → Show what would be done without submitting jobs")
    console.print()
