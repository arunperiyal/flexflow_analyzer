# FlexFlow Changelog

## Unreleased

### ✨ New Features

#### Command Chaining with Semicolons
- **Semicolon separator** - Chain multiple commands on one line
  - Example: `use case:Case005; data show --pendulum; plot --data-type pendulum`
  - Supports quoted strings: `plot --title "A; B"; data show`
  - Empty commands ignored (e.g., `cmd1;; cmd2`)
- **Smart tab completion** - Tab works correctly after semicolons
- **Context persistence** - Context set by `use` applies to all chained commands
- **Error handling** - Errors in one command don't stop the chain

#### Pendulum Data Support
- **`--pendulum` flag** - Added to `data show` command to display pendulum data
- **`pendulum` data type** - Added to `plot` command's `--data-type` option
- **New components** - Pendulum: displacement, velocity, acceleration, all
- **Pendulum plotting** - Time-series and FFT plots for pendulum data
- **Full documentation** - Help messages and examples updated

## Version 2.0.0 - Interactive Shell Release (2026-02-06)

### 🎉 Major Features

#### Interactive Shell Mode
- **Always-on REPL interface** - No more startup overhead between commands
- **Instant command execution** - Commands run 20x faster after initial load
- **Persistent command history** - History saved across sessions in `~/.flexflow/history`
- **Smart tab completion** - Complete commands, subcommands, and options
- **Professional UI** - Rich terminal formatting with colors, tables, and panels

#### File System Browsing
- **`ls` command** - List files with color coding and multiple formats
  - `ls` - Simple column view
  - `ls -l` - Long format with size, date, and type
  - `ls -a` - Show hidden files
  - `ll` - Alias for `ls -l`
  - `la` - Alias for `ls -a`
- **`cd` command** - Navigate directories
  - `cd <path>` - Change to any directory
  - `cd ~` or `cd` - Go to home directory
  - `cd ..` - Go to parent directory
- **`pwd` command** - Show current directory and case context
- **`find` command** - Search for FlexFlow case directories recursively
- **`tree` command** - Display directory structure with visual guides
  - `tree` - Show tree with depth 2 (default)
  - `tree <depth>` - Show tree with custom depth

#### Smart Case Detection
- Automatically identifies FlexFlow case directories
- Color codes cases in green in listings
- Detects based on:
  - Presence of `input/`, `output/`, `binary/` directories
  - Configuration files (`simflow.config`, `case.config`)
  - Data files (`.othd`, `.oisd`, `.plt`)

#### Case Context Management
- **`use <case>` command** - Set current case context
  - Automatically resolves relative and absolute paths
  - Injects case into commands when appropriate
  - Shows case name in shell prompt
- **Smart case injection** - Commands automatically use current case when set
  - `case show` - Uses current case
  - `data show` - Uses current case
  - `plot` - Uses current case
  - `field info` - Uses current case

#### Enhanced Shell Commands
- **`help` or `?`** - Show all available commands with descriptions
- **`exit` or `quit`** - Exit FlexFlow (also Ctrl+D)
- **`clear`** - Clear the screen (also Ctrl+L)
- **`history`** - Show command history (last 20 commands)

### 🏗️ Architecture Improvements

#### Code Refactoring
- **Minimal `main.py`** - Reduced from 133 to 32 lines
- **`src/cli/app.py`** - New application class with clean separation
- **`src/cli/interactive.py`** - Complete interactive shell implementation
- **Style guide compliance** - Following PEP 8 + Google Style Guide

#### Documentation
- **`STYLE_GUIDE.md`** - Comprehensive Python coding standards (400+ lines)
- **`INTERACTIVE_MODE.md`** - Complete interactive mode guide (500+ lines)
- **`BROWSING_GUIDE.md`** - File system browsing documentation (600+ lines)
- **Updated README.md** - Reflects new interactive mode
- **Updated docs/USAGE.md** - Enhanced with interactive examples

### 📦 Dependencies
- Added `prompt_toolkit>=3.0.43` - Powers the interactive shell

### 🎨 User Experience

#### Visual Enhancements
- **Color-coded file types**:
  - Blue - Directories
  - Green - Case directories
  - Magenta - Data files (`.othd`, `.oisd`, `.plt`)
  - White - Regular files
- **Smart prompt** - Shows current directory and case
  - Abbreviated paths for long directories
  - Home directory shown as `~`
  - Current case in brackets `[CS4SG1U1]`
- **Human-readable file sizes** - KB, MB, GB formatting
- **Formatted tables** - Rich tables for listings and information

#### Keyboard Shortcuts
- `Tab` - Auto-complete commands (partial path completion planned)
- `↑/↓` - Navigate command history
- `Ctrl+R` - Reverse search history
- `Ctrl+C` - Cancel current line (doesn't exit)
- `Ctrl+D` - Exit shell
- `Ctrl+L` - Clear screen

### 🚀 Performance
- **First command**: ~2 seconds (same as before)
- **Subsequent commands**: <0.1 seconds (20x faster)
- **Memory**: ~150 MB (persistent, more efficient overall)
- **No reload overhead**: All modules stay loaded

### 📝 Workflows Enabled

#### Quick Analysis
```bash
$ ff
flexflow → cd ~/simulations
flexflow ~/simulations → find CS4
flexflow ~/simulations → use CS4SG1U1
flexflow ~/simulations [CS4SG1U1] → case show
flexflow ~/simulations [CS4SG1U1] → plot --node 10
```

#### Cross-Project Comparison
```bash
flexflow /project1 → case show CS4SG1U1
flexflow /project1 → cd /project2
flexflow /project2 → case show CS4SG2U1
```

#### Exploration
```bash
flexflow → cd /data/new_simulations
flexflow /data/new_simulations → tree 2
flexflow /data/new_simulations → find
flexflow /data/new_simulations → ls -l
```

### 🔧 Technical Details

#### File Structure
```
src/
├── cli/
│   ├── app.py              # Application class
│   ├── interactive.py      # Interactive shell (900+ lines)
│   ├── registry.py         # Command registry
│   ├── help_messages.py    # Help system
│   └── completion.py       # Shell completion
├── commands/               # Command implementations
├── core/                   # Core data structures
└── utils/                  # Utilities

docs/
├── INDEX.md               # Documentation hub
├── USAGE.md               # Usage guide
└── technical/             # Technical docs

Root:
├── main.py                # Minimal entry point
├── STYLE_GUIDE.md         # Coding standards
├── INTERACTIVE_MODE.md    # Interactive guide
├── BROWSING_GUIDE.md      # Browsing guide
└── README.md              # Project overview
```

### 🔄 Migration

#### For Users
**Old way:**
```bash
ff case show CS4SG1U1
ff data show CS4SG1U1
```

**New way:**
```bash
ff
flexflow → use CS4SG1U1
flexflow [CS4SG1U1] → case show
flexflow [CS4SG1U1] → data show
```

#### For Scripts
**Old script:**
```bash
#!/bin/bash
ff case show CS4SG1U1
ff data show CS4SG1U1
```

**New script:**
```bash
#!/bin/bash
ff << EOF
use CS4SG1U1
case show
data show
exit
EOF
```

### ⚠️ Breaking Changes
- FlexFlow now always runs in interactive mode
- Direct command execution (`ff case show CS4SG1U1`) no longer supported
  - Must use heredoc or pipe for scripting
- Command history now in `~/.flexflow/history` instead of shell history

### 🎯 Future Enhancements

#### Planned for v2.1.0
- [ ] Tab completion for file paths
- [ ] Tab completion for case names
- [ ] `cd -` to return to previous directory
- [ ] Directory bookmarks
- [ ] Command aliases (custom shortcuts)

#### Planned for v2.2.0
- [ ] Multi-line command editing
- [ ] Syntax highlighting in commands
- [ ] Plugins system
- [ ] Custom themes
- [ ] Configuration file (`~/.flexflow/config.yaml`)

#### Under Consideration
- [ ] Scripting mini-language
- [ ] Batch operations
- [ ] Remote case access
- [ ] Case templates management
- [ ] Integrated plotting preview

### 🐛 Bug Fixes
- Fixed: Parser creation logic moved out of `main.py`
- Fixed: Module-level instantiation removed (style guide compliance)
- Fixed: Case context now properly resolved to full paths
- Fixed: System exit codes properly handled in interactive mode

### 📚 Documentation

#### New Documents
- `STYLE_GUIDE.md` - Python coding standards
- `INTERACTIVE_MODE.md` - Interactive shell guide
- `BROWSING_GUIDE.md` - File browsing guide
- `CHANGELOG.md` - This file

#### Updated Documents
- `README.md` - Now reflects interactive mode
- `docs/USAGE.md` - Enhanced with interactive examples
- `docs/INDEX.md` - Updated structure

### 👥 Contributors
- Architecture design and implementation
- Interactive shell with prompt_toolkit
- File system browsing commands
- Smart case detection
- Comprehensive documentation

### 🙏 Acknowledgments
- **prompt_toolkit** - Excellent readline replacement
- **rich** - Beautiful terminal formatting
- **Python community** - For PEP 8 and style guidelines

---

## Version 1.x (Previous)

### Version 1.0.0 - Initial Release
- Basic command-line interface
- Case analysis commands
- Data inspection
- Plotting capabilities
- SLURM job submission

---

**For complete documentation, see:**
- [Interactive Mode Guide](INTERACTIVE_MODE.md)
- [Browsing Guide](BROWSING_GUIDE.md)
- [Usage Guide](docs/USAGE.md)
- [Style Guide](STYLE_GUIDE.md)
