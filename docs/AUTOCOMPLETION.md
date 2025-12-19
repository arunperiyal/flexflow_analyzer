# FlexFlow Shell Autocompletion

FlexFlow provides comprehensive tab completion support for Bash, Zsh, and Fish shells, making it easier to discover commands, options, and arguments.

## Features

- **Command completion**: Complete main commands (`info`, `plot`, `compare`, etc.)
- **Flag completion**: Complete options like `--data-type`, `--plot-type`, `--component`
- **Value completion**: Complete specific values (e.g., `displacement`, `force` for `--data-type`)
- **Case directory completion**: Automatically complete case directories (CS*, *U*)
- **File completion**: Complete file paths for `--output` and `--input-file`
- **Context-aware**: Only shows relevant options based on the current command

## Installation

### Automatic Installation (Recommended)

During FlexFlow installation, autocompletion is automatically set up:

```bash
python main.py --install
```

The installer will:
1. Detect your shell (bash, zsh, or fish)
2. Ask if you want to install tab completion
3. Install the completion script to the appropriate location
4. Provide instructions for enabling it

### Manual Installation

#### Bash

**User-level installation (recommended - no sudo needed)**
```bash
# Create completion directory
mkdir -p ~/.bash_completion.d

# Generate and save completion script
flexflow --completion bash > ~/.bash_completion.d/flexflow

# Add to your ~/.bashrc
echo '[[ -f ~/.bash_completion.d/flexflow ]] && source ~/.bash_completion.d/flexflow' >> ~/.bashrc

# Reload
source ~/.bashrc
```

**Note:** The automatic installer always uses user directories (`~/.bash_completion.d`) to avoid requiring root permissions.

#### Zsh

```bash
# Create completion directory
mkdir -p ~/.zsh/completion

# Generate and save completion script
flexflow --completion zsh > ~/.zsh/completion/_flexflow

# Add to your ~/.zshrc (if not already present)
echo 'fpath=(~/.zsh/completion $fpath)' >> ~/.zshrc
echo 'autoload -Uz compinit && compinit' >> ~/.zshrc

# Reload
source ~/.zshrc
```

#### Fish

```bash
# Create completion directory
mkdir -p ~/.config/fish/completions

# Generate and save completion script
flexflow --completion fish > ~/.config/fish/completions/flexflow.fish

# Reload (or restart fish)
```

## Usage Examples

### Basic Command Completion

```bash
# Type and press TAB to see all commands
$ flexflow <TAB>
info  plot  compare  template  docs  statistics  preview

# Type partial command and TAB to complete
$ flexflow pl<TAB>
$ flexflow plot
```

### Option Completion

```bash
# Press TAB after -- to see all available options
$ flexflow plot --<TAB>
--component      --input-file     --plot-style     --ylabel
--data-type      --legend         --plot-type      ...

# Type partial option and TAB to complete
$ flexflow plot --data-<TAB>
$ flexflow plot --data-type
```

### Value Completion

```bash
# Complete data types
$ flexflow plot CS4SG1U1 --data-type <TAB>
displacement  force  moment  pressure

# Complete components
$ flexflow plot CS4SG1U1 --component <TAB>
x  y  z  magnitude  tx  ty  tz  all

# Complete plot types
$ flexflow plot CS4SG1U1 --plot-type <TAB>
time  fft  traj2d  traj3d
```

### Case Directory Completion

```bash
# Complete case directories (automatically finds CS* and *U* directories)
$ flexflow info <TAB>
CS4SG1U1/  CS4SG2U1/

$ flexflow compare <TAB>
CS4SG1U1/  CS4SG2U1/
```

### File Completion

```bash
# Complete YAML configuration files
$ flexflow plot --input-file <TAB>
config.yaml  example_single_config.yaml  example_multi_config.yaml

# Complete output file paths
$ flexflow plot --output <TAB>
results/  figures/  output.pdf
```

## Advanced Features

### Context-Aware Completion

The completion system is context-aware and only shows relevant options:

```bash
# After selecting a command, only that command's options are shown
$ flexflow plot --<TAB>
# Shows plot-specific options

$ flexflow compare --<TAB>
# Shows compare-specific options (different from plot)
```

### Multi-Value Completion

For commands that accept multiple values (like `compare`), completion works for each value:

```bash
$ flexflow compare CS4SG1U1 <TAB>
CS4SG2U1/  # Can add more cases

$ flexflow compare CS4SG1U1 CS4SG2U1 <TAB>
# Still shows more case options
```

### Chained Completion

You can use completion at any point in the command:

```bash
$ flexflow plot <TAB> --data-type <TAB> --component <TAB>
# Each TAB shows relevant completions at that position
```

## Completion Features by Command

### `info` Command
- Case directories
- Flags: `-v`, `--verbose`, `-h`, `--help`, `--examples`

### `preview` Command
- Case directories
- Flags: `--node`, `--start-time`, `--end-time`, `-v`, `--verbose`, `-h`, `--help`, `--examples`

### `statistics` Command
- Case directories
- Flags: `--node`, `-v`, `--verbose`, `-h`, `--help`, `--examples`

### `plot` Command
- Case directories
- Data types: `displacement`, `force`, `moment`, `pressure`
- Components: `x`, `y`, `z`, `magnitude`, `tx`, `ty`, `tz`, `all`
- Plot types: `time`, `fft`, `traj2d`, `traj3d`
- File paths for `--input-file` and `--output`
- All plot-specific flags

### `compare` Command
- Multiple case directories
- Same data types, components, and plot types as `plot`
- Comparison-specific flags like `--subplot`

### `template` Command
- Template types: `single`, `multi`, `fft`
- File paths for `--output`
- Flags: `--force`, `-v`, `--verbose`, `-h`, `--help`

### `docs` Command
- Documentation topics: `main`, `plot`, `compare`, `info`, `template`, `statistics`, `preview`

## Troubleshooting

### Completion Not Working

1. **Verify completion is installed:**
   ```bash
   # For bash
   ls -la ~/.bash_completion.d/flexflow
   
   # For zsh
   ls -la ~/.zsh/completion/_flexflow
   
   # For fish
   ls -la ~/.config/fish/completions/flexflow.fish
   ```

2. **Check if it's sourced:**
   ```bash
   # For bash
   grep flexflow ~/.bashrc
   
   # For zsh
   grep flexflow ~/.zshrc
   ```

3. **Reload shell configuration:**
   ```bash
   # Bash
   source ~/.bashrc
   
   # Zsh
   source ~/.zshrc
   
   # Fish - restart the shell
   exec fish
   ```

4. **Verify FlexFlow is in PATH:**
   ```bash
   which flexflow
   # Should show the path to flexflow
   ```

### Permission Denied During Installation

The installer uses user directories (`~/.bash_completion.d`, `~/.zsh/completion`, etc.) which don't require sudo. If you still encounter permission issues:

```bash
# Bash
mkdir -p ~/.bash_completion.d
chmod 755 ~/.bash_completion.d
flexflow --completion bash > ~/.bash_completion.d/flexflow
echo '[[ -f ~/.bash_completion.d/flexflow ]] && source ~/.bash_completion.d/flexflow' >> ~/.bashrc

# Zsh
mkdir -p ~/.zsh/completion
chmod 755 ~/.zsh/completion
flexflow --completion zsh > ~/.zsh/completion/_flexflow
echo 'fpath=(~/.zsh/completion $fpath)' >> ~/.zshrc
echo 'autoload -Uz compinit && compinit' >> ~/.zshrc

# Fish
mkdir -p ~/.config/fish/completions
flexflow --completion fish > ~/.config/fish/completions/flexflow.fish
```

### Completion Shows Wrong Options

- **Clear completion cache (Zsh):**
  ```bash
  rm -f ~/.zcompdump*
  compinit
  ```

- **Reload completion script:**
  ```bash
  source ~/.bashrc  # or ~/.zshrc
  ```

### Case Directories Not Completing

The completion looks for directories matching these patterns:
- `CS*` (e.g., CS4SG1U1, CS4SG2U1)
- `*U*` (e.g., SG1U1, SG2U1)

Make sure your case directories follow this naming convention or are in the current directory.

## Generating Completion Scripts

You can generate completion scripts without installing:

```bash
# Generate bash completion
flexflow --completion bash

# Generate zsh completion
flexflow --completion zsh

# Generate fish completion
flexflow --completion fish

# Save to a file
flexflow --completion bash > flexflow-completion.bash
```

This is useful for:
- Manual installation
- Distributing completion scripts
- Custom installation locations
- Testing modifications

## Shell-Specific Notes

### Bash
- Requires `bash-completion` package for best experience
- Works with Bash 4.0+
- Uses `complete -F` for programmable completion

### Zsh
- Utilizes Zsh's powerful `compdef` system
- Supports rich descriptions for options
- Automatically caches completions for better performance

### Fish
- Fish has built-in completion system
- Completions are automatically loaded from `~/.config/fish/completions/`
- No additional configuration needed after installation

## Uninstalling Completion

To remove autocompletion:

```bash
# Uninstall everything including completion
flexflow --uninstall

# Or manually remove completion files
rm ~/.bash_completion.d/flexflow  # Bash
rm ~/.zsh/completion/_flexflow     # Zsh
rm ~/.config/fish/completions/flexflow.fish  # Fish
```

## Tips for Power Users

1. **Use completion to discover features:**
   ```bash
   flexflow plot --<TAB><TAB>
   # Shows all available plot options
   ```

2. **Combine with help:**
   ```bash
   flexflow plot --help
   # Then use completion to fill in the options
   ```

3. **Quick case exploration:**
   ```bash
   flexflow info <TAB>
   # Shows all available case directories
   ```

4. **Template discovery:**
   ```bash
   flexflow template <TAB>
   # Shows template types: single, multi, fft
   ```

## Contributing

If you find issues with completion or want to add support for more shells:
1. The completion code is in `module/cli/completion.py`
2. Test your changes with all supported shells
3. Submit a pull request with your improvements

## See Also

- [FlexFlow Main Documentation](../README.md)
- [Installation Guide](INSTALLATION.md)
- [Usage Guide](USAGE.md)
