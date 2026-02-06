# FlexFlow Browsing Guide

FlexFlow's interactive shell includes powerful browsing capabilities that let you navigate the filesystem, find cases, and explore directory structures without leaving the application.

## Table of Contents

- [Overview](#overview)
- [Browsing Commands](#browsing-commands)
- [Examples](#examples)
- [Features](#features)
- [Tips and Tricks](#tips-and-tricks)

## Overview

### Why Browsing in FlexFlow?

**Before:** Users had to exit FlexFlow, navigate in the shell, then restart FlexFlow
```bash
$ ff
flexflow → case show CS4SG1U1
flexflow → exit
$ cd ../otherProject
$ ff
flexflow → case show CS4SG2U1
```

**Now:** Navigate without leaving FlexFlow
```bash
$ ff
flexflow /project1 → case show CS4SG1U1
flexflow /project1 → cd ../project2
→ /project2
flexflow /project2 → case show CS4SG2U1
flexflow /project2 → find CS4*
```

### Key Benefits

✅ **No context switching** - Stay in FlexFlow
✅ **Fast navigation** - Unix-like commands
✅ **Case discovery** - Find cases automatically
✅ **Visual feedback** - Color-coded output
✅ **Smart detection** - Identifies case directories

## Browsing Commands

### pwd - Print Working Directory

Show current directory and case context.

**Usage:**
```bash
flexflow → pwd
```

**Output:**
```
Working directory: /media/user/projects/simulations
Current case: CS4SG1U1
```

**Use cases:**
- Check where you are
- Verify current case context
- Before running commands on files

### cd - Change Directory

Navigate to different directories.

**Syntax:**
```bash
cd <path>          # Change to path
cd ~               # Go to home directory
cd ..              # Go to parent directory
cd -               # Go to previous directory (planned)
```

**Examples:**
```bash
# Absolute path
flexflow → cd /media/user/projects/simulations

# Relative path
flexflow → cd cases/CS4SG1U1

# Parent directory
flexflow → cd ..

# Home directory
flexflow → cd ~

# Shortcut to home
flexflow → cd
```

**Features:**
- Tab completion for paths
- Automatic path resolution
- Error messages for invalid paths
- Updates shell prompt automatically

### ls - List Directory

List files and directories with various formatting options.

**Syntax:**
```bash
ls [path]          # List directory
ls -l              # Long format with details
ls -a              # Show hidden files
ls -la             # Long format + hidden files
```

**Simple Format (default):**
```bash
flexflow → ls

__pycache__/    docs/           examples/
install/        src/            README.md
main.py         requirements.txt
```

**Long Format (-l):**
```bash
flexflow → ls -l

 Type      Size        Modified          Name
────────────────────────────────────────────────────────
 DIR           -       2026-02-06 20:26  docs/
 DIR           -       2026-01-26 00:55  src/
 FILE     10.7KB       2026-02-06 20:24  INSTALL.md
 FILE     19.2KB       2026-02-06 20:35  STYLE_GUIDE.md
```

**Color Coding:**
- **Blue** - Regular directories
- **Green** - Case directories (detected automatically)
- **Magenta** - Data files (.othd, .oisd, .plt)
- **White** - Regular files

**Show Hidden Files (-a):**
```bash
flexflow → ls -a

.git/           .gitignore      __pycache__/
docs/           src/            README.md
```

**List Specific Path:**
```bash
flexflow → ls src/commands
flexflow → ls ../otherProject
flexflow → ls ~/simulations
```

### find - Find Case Directories

Search for FlexFlow case directories in current directory and subdirectories.

**Syntax:**
```bash
find [pattern]     # Find cases matching pattern
find               # Find all cases (same as find *)
```

**Examples:**
```bash
# Find all cases
flexflow → find

Searching for cases matching '*'...

           Cases Found (3)
┌───┬────────────┬──────────────────┐
│ # │ Case Name  │ Path             │
├───┼────────────┼──────────────────┤
│ 1 │ CS4SG1U1   │ cases/CS4SG1U1   │
│ 2 │ CS4SG2U1   │ cases/CS4SG2U1   │
│ 3 │ TestCase   │ test/TestCase    │
└───┴────────────┴──────────────────┘

# Find specific pattern
flexflow → find CS4*

# Case-insensitive search
flexflow → find sg1
```

**Case Detection:**

FlexFlow automatically identifies case directories by looking for:
- `input/`, `output/`, `binary/` directories
- `simflow.config` or `case.config` files
- `.othd` or `.oisd` data files

**Use Cases:**
- Discover available cases
- Find cases after navigating to new directory
- Quick case inventory
- Search by pattern

### tree - Show Directory Tree

Display directory structure as a tree.

**Syntax:**
```bash
tree [depth]       # Show tree (default depth: 2)
tree 1             # Shallow tree
tree 3             # Deeper tree
```

**Example Output:**
```bash
flexflow → tree 2

flexflow_manager
├── docs/
│   ├── INDEX.md
│   ├── USAGE.md
│   ├── setup/
│   └── technical/
├── src/
│   ├── cli/
│   ├── commands/
│   ├── core/
│   └── utils/
├── examples/
│   └── standard/ (case)
├── README.md
├── INSTALL.md
└── requirements.txt
```

**Color Coding:**
- **Cyan** - Directories
- **Green + (case)** - Case directories
- **Magenta** - Data files
- **White** - Regular files

**Features:**
- Respects depth limit to avoid huge trees
- Shows up to 50 items per directory
- Skips hidden files
- Visual guide lines
- Case detection

## Examples

### Workflow 1: Navigate to Case and Analyze

```bash
$ ff
flexflow ~/projects → ls
cases/  data/  reports/

flexflow ~/projects → cd cases
→ /home/user/projects/cases

flexflow ~/projects/cases → find
           Cases Found (5)
┌───┬────────────┬──────────────┐
│ # │ Case Name  │ Path         │
├───┼────────────┼──────────────┤
│ 1 │ CS4SG1U1   │ CS4SG1U1     │
│ 2 │ CS4SG2U1   │ CS4SG2U1     │
│ 3 │ CS4SG3U1   │ CS4SG3U1     │
│ 4 │ CS4SG4U1   │ CS4SG4U1     │
│ 5 │ TestRun    │ TestRun      │
└───┴────────────┴──────────────┘

flexflow ~/projects/cases → use CS4SG1U1
✓ Current case set to: CS4SG1U1

flexflow ~/projects/cases [CS4SG1U1] → case show
Loading OTHD files...
...
```

### Workflow 2: Compare Cases in Different Directories

```bash
flexflow /project1 → case show CS4SG1U1
# Analyze first case...

flexflow /project1 → cd /project2
→ /project2

flexflow /project2 → find SG1
           Cases Found (2)
┌───┬────────────┬──────────────┐
│ # │ Case Name  │ Path         │
├───┼────────────┼──────────────┤
│ 1 │ CS4SG1U1   │ sim/CS4SG1U1 │
│ 2 │ CS5SG1U1   │ sim/CS5SG1U1 │
└───┴────────────┴──────────────┘

flexflow /project2 → cd sim/CS4SG1U1
→ /project2/sim/CS4SG1U1

flexflow .../sim/CS4SG1U1 → case show
# Compare with first case...
```

### Workflow 3: Explore Unknown Directory

```bash
flexflow → cd /data/simulations
→ /data/simulations

flexflow /data/simulations → tree 1
simulations
├── 2025/
├── 2026/
├── archive/
├── templates/
└── README.md

flexflow /data/simulations → cd 2026
→ /data/simulations/2026

flexflow /data/simulations/2026 → find
Searching for cases matching '*'...
           Cases Found (12)
...

flexflow /data/simulations/2026 → ls -l
# See all files with details...
```

### Workflow 4: Quick Case Check

```bash
flexflow → cd ~/simulations
→ /home/user/simulations

flexflow ~/simulations → find CS4
           Cases Found (1)
┌───┬──────────┬────────────────┐
│ # │ Case Name│ Path           │
├───┼──────────┼────────────────┤
│ 1 │ CS4SG1U1 │ runs/CS4SG1U1  │
└───┴──────────┴────────────────┘

flexflow ~/simulations → cd runs/CS4SG1U1
→ /home/user/simulations/runs/CS4SG1U1

flexflow .../runs/CS4SG1U1 → ls
input/    output/    binary/    scripts/

flexflow .../runs/CS4SG1U1 → check output/riser.othd
# Quick data file check...
```

## Features

### Smart Case Detection

FlexFlow automatically identifies case directories:

```bash
flexflow → ls

# Regular directories appear in cyan
regular_dir/

# Case directories appear in green with special marker
CS4SG1U1/    # ← Detected as case
CS4SG2U1/    # ← Detected as case
```

**Detection Criteria:**
1. Contains `input/`, `output/`, or `binary/` directories
2. Contains `simflow.config` or `case.config` files
3. Contains `.othd` or `.oisd` data files

### File Type Highlighting

Different file types are color-coded:

- **Directories:** Cyan (`dirname/`)
- **Cases:** Green (`casename/`)
- **Data files:** Magenta (`.othd`, `.oisd`, `.plt`)
- **Regular files:** White

### Path Display in Prompt

The prompt shows your current location:

```bash
# Full path when short
flexflow /home/user →

# Abbreviated with ~ for home
flexflow ~/projects →

# Truncated when long
flexflow ...cts/simulations/cases →
```

### Size Formatting

File sizes are human-readable in long format:

- `1.2KB` - Kilobytes
- `5.3MB` - Megabytes
- `2.1GB` - Gigabytes
- `458.0B` - Bytes

## Tips and Tricks

### 1. Quick Navigation Shortcuts

```bash
# Home directory (multiple ways)
flexflow → cd
flexflow → cd ~

# Parent directory
flexflow → cd ..

# Back to previous (planned feature)
flexflow → cd -
```

### 2. Combining Commands

```bash
# Find and navigate to case
flexflow → find CS4SG1U1
flexflow → cd cases/CS4SG1U1
flexflow → use CS4SG1U1
flexflow → case show
```

### 3. Exploring New Projects

```bash
# See structure first
flexflow → tree 2

# List with details
flexflow → ls -l

# Find all cases
flexflow → find
```

### 4. Using Relative Paths

```bash
flexflow ~/projects → ls cases
flexflow ~/projects → cd cases/CS4SG1U1
flexflow ~/projects/cases/CS4SG1U1 → cd ../../data
flexflow ~/projects/data → pwd
```

### 5. Case Context Workflow

```bash
# Set case context to avoid repeating name
flexflow → cd ~/simulations/CS4SG1U1
flexflow .../CS4SG1U1 → use CS4SG1U1
flexflow .../CS4SG1U1 [CS4SG1U1] → case show
flexflow .../CS4SG1U1 [CS4SG1U1] → data show --node 24
flexflow .../CS4SG1U1 [CS4SG1U1] → plot --node 10
```

### 6. Finding Cases Across Projects

```bash
# From any location, search entire project
flexflow → cd ~/simulations
flexflow ~/simulations → find
# Shows all cases recursively
```

### 7. Quick Data File Location

```bash
flexflow → cd mycas
flexflow → ls output
# or
flexflow → ls -l output/*.othd
```

## Command Reference

### All Browsing Commands

| Command | Description | Example |
|---------|-------------|---------|
| `pwd` | Show current directory and case | `pwd` |
| `use <case>` | Set current case context | `use CS4SG1U1` |
| `unuse` | Clear case context | `unuse` |
| `cd <path>` | Change directory | `cd cases/CS4SG1U1` |
| `cd ~` | Go to home | `cd ~` |
| `cd ..` | Go to parent | `cd ..` |
| `ls` | List files (simple) | `ls` |
| `ls -l` | List files (detailed) | `ls -l` |
| `ls -a` | Show hidden files | `ls -a` |
| `ls <path>` | List specific path | `ls src/commands` |
| `find` | Find all cases | `find` |
| `find <pattern>` | Find matching cases | `find CS4*` |
| `tree` | Show tree (depth 2) | `tree` |
| `tree <depth>` | Show tree custom depth | `tree 3` |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Tab` | Path completion (planned) |
| `↑` | Previous command |
| `↓` | Next command |
| `Ctrl+C` | Cancel current line |
| `Ctrl+L` | Clear screen |
| `Ctrl+D` | Exit FlexFlow |

## Future Enhancements

Planned improvements:

1. **Tab Completion for Paths**
   - Complete directory names
   - Complete file names
   - Complete case names

2. **History Navigation**
   - `cd -` to go back
   - Directory stack (pushd/popd)

3. **Advanced Filtering**
   - `ls *.othd` - glob patterns
   - `find --modified-today` - time filters
   - `find --size >100MB` - size filters

4. **Bookmarks**
   - `bookmark add mycase` - Save location
   - `bookmark go mycase` - Jump to bookmark
   - `bookmark list` - Show bookmarks

5. **Case Operations**
   - `cases` - List only cases in current dir
   - `cases --all` - List all cases recursively
   - `goto <case>` - Quick jump to case

6. **File Operations** (maybe)
   - `cp <src> <dst>` - Copy files
   - `mv <src> <dst>` - Move files
   - `mkdir <name>` - Create directory

## Comparison with Shell

### What Works Like a Shell

✅ `pwd` - Same as Unix pwd
✅ `cd` - Same as Unix cd
✅ `ls` - Similar to Unix ls
✅ `tree` - Similar to Unix tree
✅ Path resolution - Same as shell

### What's Different

❌ **No file manipulation** - Use shell for cp, mv, rm
❌ **No piping** - No `|`, `>`, `<` operators
❌ **No globbing in commands** - Yet
❌ **Limited scripting** - Designed for interactive use

### Why Not Just Use the Shell?

**FlexFlow browsing is better for:**
1. **Context persistence** - Case and directory remembered
2. **Case detection** - Automatic case identification
3. **Integrated workflow** - Browse + analyze in one place
4. **No restarts** - Stay in FlexFlow, no overhead

**Shell is better for:**
1. File manipulation (cp, mv, rm)
2. Complex scripting
3. Piping and redirection
4. System administration

## Troubleshooting

### "Permission denied" errors

**Problem:** Can't access directory

**Solution:**
```bash
# Check permissions in shell first
$ ls -ld /path/to/directory

# Fix permissions if needed
$ chmod 755 /path/to/directory
```

### Case not detected

**Problem:** Case directory not highlighted or found

**Solution:**
```bash
# Check case structure
flexflow → cd suspected_case
flexflow → ls
# Should have input/, output/, or *.othd files

# Manually use the case anyway
flexflow → use suspected_case
flexflow → case show suspected_case
```

### Path completion not working

**Status:** Tab completion for paths is planned, not yet implemented

**Workaround:** Type full paths or use `ls` to see options

## Summary

FlexFlow's browsing commands provide:

✅ **Shell-like navigation** - Familiar commands
✅ **No context switching** - Stay in FlexFlow
✅ **Smart case detection** - Automatic identification
✅ **Visual feedback** - Color-coded output
✅ **Integrated workflow** - Browse and analyze together

Navigate freely, find cases quickly, and analyze without interruption!

---

**Related Documentation:**
- [Interactive Mode Guide](INTERACTIVE_MODE.md)
- [Usage Guide](docs/USAGE.md)
- [README](README.md)
