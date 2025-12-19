# FlexFlow Autocompletion - Quick Start

Tab completion makes FlexFlow easier to use by suggesting commands, options, and values as you type.

## Quick Setup

### During Installation
```bash
python main.py --install
# Select 'y' when prompted to install tab completion
```

### After Installation
Restart your shell or run:
```bash
# For Bash
source ~/.bashrc

# For Zsh
source ~/.zshrc

# For Fish
exec fish
```

## Quick Test

Try these commands and press TAB where indicated:

```bash
# See all commands
flexflow <TAB>

# See all plot options
flexflow plot --<TAB>

# Complete data types
flexflow plot --data-type <TAB>
# Shows: displacement force moment pressure

# Complete components
flexflow plot --component <TAB>
# Shows: x y z magnitude tx ty tz all

# See available case directories
flexflow info <TAB>
```

## Common Completions

| Context | Press TAB After | Shows |
|---------|----------------|-------|
| Commands | `flexflow ` | info, plot, compare, template, docs, statistics, preview |
| Data Types | `--data-type ` | displacement, force, moment, pressure |
| Components | `--component ` | x, y, z, magnitude, tx, ty, tz, all |
| Plot Types | `--plot-type ` | time, fft, traj2d, traj3d |
| Templates | `template ` | single, multi, fft |
| Case Dirs | Command arguments | CS*, *U* directories |

## Manual Installation

If autocompletion wasn't installed during setup:

### Bash
```bash
mkdir -p ~/.bash_completion.d
flexflow --completion bash > ~/.bash_completion.d/flexflow
echo '[[ -f ~/.bash_completion.d/flexflow ]] && source ~/.bash_completion.d/flexflow' >> ~/.bashrc
source ~/.bashrc
```

### Zsh
```bash
mkdir -p ~/.zsh/completion
flexflow --completion zsh > ~/.zsh/completion/_flexflow
echo 'fpath=(~/.zsh/completion $fpath)' >> ~/.zshrc
echo 'autoload -Uz compinit && compinit' >> ~/.zshrc
source ~/.zshrc
```

### Fish
```bash
mkdir -p ~/.config/fish/completions
flexflow --completion fish > ~/.config/fish/completions/flexflow.fish
# Restart fish shell
```

## Troubleshooting

**Completion not working?**

1. Check if FlexFlow is in your PATH:
   ```bash
   which flexflow
   ```

2. Verify completion script exists:
   ```bash
   ls ~/.bash_completion.d/flexflow      # Bash
   ls ~/.zsh/completion/_flexflow        # Zsh
   ls ~/.config/fish/completions/flexflow.fish  # Fish
   ```

3. Check if it's sourced in your shell config:
   ```bash
   grep flexflow ~/.bashrc  # or ~/.zshrc
   ```

4. Reload your shell configuration:
   ```bash
   source ~/.bashrc  # or ~/.zshrc
   ```

**Permission denied during installation?**

The installer now uses user directories (`~/.bash_completion.d`) which don't require sudo. If you still see permission errors, try:
```bash
mkdir -p ~/.bash_completion.d
flexflow --completion bash > ~/.bash_completion.d/flexflow
echo '[[ -f ~/.bash_completion.d/flexflow ]] && source ~/.bash_completion.d/flexflow' >> ~/.bashrc
source ~/.bashrc
```

**Still not working?**

See the [full documentation](docs/AUTOCOMPLETION.md) for detailed troubleshooting.

## More Information

- Full documentation: `docs/AUTOCOMPLETION.md`
- FlexFlow help: `flexflow --help`
- Command help: `flexflow <command> --help`

---

**Pro Tip:** Use TAB completion to discover FlexFlow features you didn't know existed!
