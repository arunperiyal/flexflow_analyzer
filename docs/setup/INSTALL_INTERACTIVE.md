# FlexFlow Installation Guide

## Quick Start

FlexFlow provides an **interactive installation script** that handles everything automatically.

### One-Command Installation

```bash
cd /path/to/flexflow_manager
./install.sh
```

The script will:
1. ✅ Check for Anaconda/Miniconda
2. ✅ Create Python 3.12 environment
3. ✅ Install all dependencies
4. ✅ Setup FlexFlow command
5. ✅ Configure shell aliases
6. ✅ Setup tab completion (optional)

## Installation Options

The installer offers **4 installation types**:

### Option 1: Fast Alias (Recommended)

**Best for:** Development and daily use

- Creates `ff` alias for instant access
- Startup time: 0.4 seconds ⚡⚡⚡
- Uses source code directly
- Easy to update

```bash
# After installation:
ff -v                    # Version info
ff case show CS4SG1U1   # Case analysis
```

### Option 2: User Installation

**Best for:** Single user, no sudo access

- Installs to `~/.local/bin`
- Available only to your user
- No sudo required

```bash
# After installation:
flexflow -v
flexflow case show CS4SG1U1
```

### Option 3: System Installation

**Best for:** Multi-user systems

- Installs to `/usr/local/bin`
- Available to all users
- Requires sudo

```bash
# After installation (all users):
flexflow -v
flexflow case show CS4SG1U1
```

### Option 4: Both Alias + Wrapper

**Best for:** Maximum flexibility

- Fast alias `ff` for quick commands
- Wrapper `flexflow` for convenience
- Best of both worlds!

```bash
# Fast version:
ff -v                   # 0.4s

# Wrapper version:
flexflow -v            # 0.75s
```

## Detailed Installation Steps

### Prerequisites

1. **Anaconda or Miniconda** must be installed
   - Miniconda: https://docs.conda.io/en/latest/miniconda.html
   - Anaconda: https://www.anaconda.com/products/distribution

2. **Bash shell** (Linux/macOS)

### Installation Process

1. **Download FlexFlow:**
   ```bash
   git clone https://github.com/arunperiyal/flexflow_analyzer.git
   cd flexflow_analyzer
   ```

2. **Run installer:**
   ```bash
   ./install.sh
   ```

3. **Follow prompts:**
   - The installer will guide you through each step
   - Answer questions interactively
   - Choose installation type

4. **Reload shell:**
   ```bash
   source ~/.bashrc   # or ~/.zshrc
   ```

5. **Test installation:**
   ```bash
   ff -v              # If you chose alias
   flexflow -v        # If you chose wrapper
   ```

## What Gets Installed?

### Python Environment

- **Name:** `tecplot312`
- **Python:** 3.12
- **Location:** `~/miniconda3/envs/tecplot312` (or anaconda3)

### Python Packages

- numpy
- matplotlib
- pandas
- pyyaml
- rich
- tqdm
- pytecplot

### FlexFlow Files

**Option 1 (Alias):**
- No files copied
- Uses source directly
- Alias added to `~/.bashrc` or `~/.zshrc`

**Option 2 (User):**
- Wrapper: `~/.local/bin/flexflow`
- Source: Original location (referenced)

**Option 3 (System):**
- Wrapper: `/usr/local/bin/flexflow`
- Source: Original location (referenced)

### Shell Configuration

The installer adds to your `~/.bashrc` or `~/.zshrc`:

```bash
# Conda initialization (if needed)
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    . "$HOME/miniconda3/etc/profile.d/conda.sh"
fi

# FlexFlow aliases
alias ff='conda activate tecplot312 && python /path/to/flexflow/main.py'
alias flexflow-dev='conda activate tecplot312 && python /path/to/flexflow/main.py'

# FlexFlow completion (optional)
if [ -f "$HOME/.bash_completion.d/flexflow_completion" ]; then
    source "$HOME/.bash_completion.d/flexflow_completion"
fi
```

## Verification

After installation, verify everything works:

```bash
# 1. Check version
ff -v                           # Should show FlexFlow 2.0.0

# 2. Check environment
conda env list | grep tecplot312  # Should exist

# 3. Test a command
ff case show CS4SG1U1           # Should show case info

# 4. Check Python packages
conda activate tecplot312
python -c "import tecplot; print('pytecplot OK')"
```

## Troubleshooting

### Conda not found

If installer says "Conda not found":

```bash
# Check common locations
ls -d ~/miniconda3 ~/anaconda3

# If found, source it manually
source ~/miniconda3/etc/profile.d/conda.sh
./install.sh
```

### Alias not working

If `ff` command not found:

```bash
# Reload shell config
source ~/.bashrc    # or ~/.zshrc

# Or close and reopen terminal

# Check if alias exists
alias | grep ff
```

### Permission denied

If you get "Permission denied":

```bash
# Make installer executable
chmod +x install.sh

# Run it
./install.sh
```

### Environment activation fails

If conda activate fails:

```bash
# Initialize conda for your shell
conda init bash    # or zsh
source ~/.bashrc
```

## Uninstallation

To remove FlexFlow:

### Remove Alias

Edit `~/.bashrc` or `~/.zshrc` and remove lines between:
```bash
# FlexFlow aliases
...
# End FlexFlow aliases
```

### Remove Environment

```bash
conda env remove -n tecplot312
```

### Remove Wrapper (if installed)

```bash
# User installation
rm ~/.local/bin/flexflow

# System installation
sudo rm /usr/local/bin/flexflow
```

### Remove Completion

```bash
rm ~/.bash_completion.d/flexflow_completion
```

## Alternative: Manual Installation

If you prefer not to use the installer:

### 1. Create environment
```bash
conda create -n tecplot312 python=3.12 -y
conda activate tecplot312
```

### 2. Install dependencies
```bash
pip install numpy matplotlib pandas pyyaml rich tqdm pytecplot
```

### 3. Create alias
```bash
echo 'alias ff="conda activate tecplot312 && python /path/to/flexflow/main.py"' >> ~/.bashrc
source ~/.bashrc
```

### 4. Test
```bash
ff -v
```

## Comparison: Install Methods

| Method | Setup | Startup | Updates | Best For |
|--------|-------|---------|---------|----------|
| **Alias** | 2 min | 0.4s | Instant | Development |
| **User** | 2 min | 0.75s | Manual | Single user |
| **System** | 3 min | 0.75s | Manual | Multi-user |
| **Standalone** | 0 min | 2.8s | Redownload | Distribution |

## FAQ

**Q: Which installation type should I choose?**  
A: For development: Alias (Option 1). For end users: System (Option 3).

**Q: Can I change installation type later?**  
A: Yes, just run `./install.sh` again and choose a different option.

**Q: Do I need to activate conda every time?**  
A: No! The alias/wrapper handles activation automatically.

**Q: Will this conflict with my existing Python?**  
A: No, it uses a separate conda environment (`tecplot312`).

**Q: Can I install for multiple users?**  
A: Yes, use Option 3 (System installation).

**Q: How do I update FlexFlow?**  
A: `git pull` in the repository, then run `./install.sh` again if needed.

## Next Steps

After installation:

1. **Read the Quick Reference:**
   ```bash
   cat docs/guides/PYTECPLOT_QUICKREF.md
   ```

2. **Try some commands:**
   ```bash
   ff case show CS4SG1U1
   ff field info CS4SG1U1
   ff plot CS4SG1U1 --node 10 --component y
   ```

3. **Explore documentation:**
   ```bash
   cat docs/INDEX.md
   ```

## Support

- **Documentation:** `docs/INDEX.md`
- **Issues:** https://github.com/arunperiyal/flexflow_analyzer/issues
- **Performance Guide:** `docs/technical/STARTUP_PERFORMANCE.md`

---

**Installation Time:** ~2-3 minutes  
**Disk Space:** ~500 MB (conda environment)  
**Prerequisites:** Anaconda/Miniconda

**Ready to start? Run:** `./install.sh`
