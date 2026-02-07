# FlexFlow Quick Reference

One-page reference for FlexFlow Interactive Shell commands.

## Starting FlexFlow

```bash
ff                    # Start interactive shell
```

## Shell Commands

| Command | Description | Example |
|---------|-------------|---------|
| `help` or `?` | Show all commands | `help` |
| `exit` or `quit` | Exit FlexFlow | `exit` |
| `clear` | Clear screen | `clear` |
| `history` | Show command history | `history` |
| `pwd` | Show current directory & case | `pwd` |

## Browsing Commands

| Command | Description | Example |
|---------|-------------|---------|
| `ls` | List files (simple) | `ls` |
| `ls -l` or `ll` | List files (detailed) | `ll` |
| `ls -a` or `la` | Show hidden files | `la` |
| `cd <path>` | Change directory | `cd cases` |
| `cd ~` or `cd` | Go to home | `cd ~` |
| `cd ..` | Go to parent | `cd ..` |
| `grep <pattern> [files]` | Search file contents | `grep error *.log` |
| `grep -i <pattern>` | Case-insensitive search | `grep -i warning file.txt` |
| `grep -r <pattern> <dir>` | Recursive search | `grep -r TODO src/` |
| `grep -l <pattern>` | Show only filenames | `grep -l error logs/` |
| `find [pattern]` | Find cases | `find CS4*` |
| `tree [depth]` | Show directory tree | `tree 2` |

## Context Management

| Command | Description | Example |
|---------|-------------|---------|
| `use case <path>` | Set current case | `use case CS4SG1U1` |
| `use problem <name>` | Set problem context | `use problem RISER_1` |
| `use rundir <path>` | Set run directory | `use rundir ./output` |
| `use <case>` | Shortcut for use case | `use CS4SG1U1` |
| `unuse case` | Clear case context | `unuse case` |
| `unuse problem` | Clear problem context | `unuse problem` |
| `unuse rundir` | Clear rundir context | `unuse rundir` |
| `unuse` | Clear all contexts | `unuse` |
| `pwd` | Show all contexts | `pwd` |

## FlexFlow Commands

### Case Management
```bash
case show              # Show case info (uses current case)
case show <case>       # Show specific case info
case create <name>     # Create new case
case run <case>        # Submit SLURM jobs
```

### Data Operations
```bash
data show              # Show data (uses current case)
data show <case>       # Show specific case data
data stats <case>      # Calculate statistics
```

### Field Operations
```bash
field info             # Show PLT info (uses current case)
field info <case>      # Show specific case PLT info
field extract <case>   # Extract field data
```

### File Inspection
```bash
check <file>           # Inspect OTHD/OISD file
```

### Visualization
```bash
plot --node 10         # Plot (uses current case)
plot <case> --node 10  # Plot specific case
compare <case1> <case2> # Compare cases
```

### Templates
```bash
template plot          # Generate plot config
template case          # Generate case config
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Tab` | Auto-complete |
| `↑` | Previous command |
| `↓` | Next command |
| `Ctrl+R` | Search history |
| `Ctrl+C` | Cancel line |
| `Ctrl+D` | Exit |
| `Ctrl+L` | Clear screen |

## Color Coding

- **Blue** - Directories
- **Green** - Case directories
- **Magenta** - Data files (`.othd`, `.oisd`, `.plt`)
- **White** - Regular files

## Common Workflows

### Quick Analysis
```bash
cd ~/simulations
find CS4
use case CS4SG1U1
use problem RISER_ANALYSIS
case show
plot --node 10
```

### Browse and Analyze
```bash
tree 2
ls -l
cd cases/CS4SG1U1
use CS4SG1U1
case show
data show --node 24
```

### Cross-Project
```bash
cd /project1
case show CS4SG1U1
cd /project2
case show CS4SG2U1
```

### Explore New Directory
```bash
cd /data/new_sims
tree 2
find
use <case_from_find>
case show
```

## Tips

1. **Use case context** - Set with `use`, then omit case name in commands
2. **Tab complete** - Press Tab to complete commands
3. **History navigation** - Use ↑/↓ to recall commands
4. **Quick help** - Type `?` for faster help than `--help`
5. **No exit needed** - Navigate freely with `cd`, no need to exit

## Examples

```bash
# Start FlexFlow
$ ff

# Navigate to simulations
flexflow → cd ~/simulations

# Find all CS4 cases
flexflow ~/simulations → find CS4
           Cases Found (3)
┌───┬──────────┬──────────┐
│ # │ Case Name│ Path     │
├───┼──────────┼──────────┤
│ 1 │ CS4SG1U1 │ cases/...│
│ 2 │ CS4SG2U1 │ cases/...│
│ 3 │ CS4SG3U1 │ cases/...│
└───┴──────────┴──────────┘

# Navigate to case
flexflow ~/simulations → cd cases/CS4SG1U1

# Set case context
flexflow .../CS4SG1U1 → use CS4SG1U1
✓ Current case set to: CS4SG1U1

# Analyze (no need to specify case)
flexflow .../CS4SG1U1 [CS4SG1U1] → case show
flexflow .../CS4SG1U1 [CS4SG1U1] → data show --node 24
flexflow .../CS4SG1U1 [CS4SG1U1] → plot --node 10 --component y

# Exit
flexflow .../CS4SG1U1 [CS4SG1U1] → exit
```

## Getting Help

- **In FlexFlow**: Type `help` or `?`
- **Command help**: `<command> --help`
- **Documentation**: See `INTERACTIVE_MODE.md`, `BROWSING_GUIDE.md`
- **Issues**: https://github.com/arunperiyal/flexflow_analyzer/issues

---

**Quick Start**: `ff` → `help` → start typing commands!
