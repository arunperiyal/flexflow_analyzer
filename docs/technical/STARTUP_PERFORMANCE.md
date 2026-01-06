# FlexFlow Startup Performance Guide

## Measured Startup Times

| Method | Startup Time | Speed | Setup Required |
|--------|--------------|-------|----------------|
| **Source (fast)** | ~0.4s | ⚡⚡⚡ | conda env |
| **Fast wrapper** | ~0.75s | ⚡⚡ | conda env |
| **Standalone** | ~2.8s | ⚡ | none |

## Why Standalone is Slower

PyInstaller standalone executables have startup overhead because they:
1. Unpack embedded Python interpreter (~40 MB)
2. Extract bundled libraries (~31 MB)
3. Initialize Python runtime
4. Load all imported modules

This happens **every time** you run the command.

## Solutions by Use Case

### For Daily Development (RECOMMENDED)

**Use source directly** - 7x faster!

```bash
# Option 1: Create alias
echo 'alias flexflow="python /media/arunperiyal/Works/projects/flexflow_manager/main.py"' >> ~/.bashrc
source ~/.bashrc

# Activate conda once
conda activate tecplot312

# Use normally
flexflow --version          # ~0.4s
flexflow case show CS4SG1U1 # ~0.4s
```

**Startup: ~0.4 seconds**

### For Convenient Use

**Use the fast wrapper** - 3x faster than standalone

```bash
# Copy to PATH
sudo cp /media/arunperiyal/Works/projects/flexflow_manager/flexflow_fast.sh /usr/local/bin/flexflow-fast

# Use it
flexflow-fast --version     # ~0.75s
flexflow-fast case show CS4SG1U1
```

**Startup: ~0.75 seconds**

### For Distribution

**Use standalone** - no setup required

```bash
# Already installed
flexflow --version          # ~2.8s
```

**Startup: ~2.8 seconds**  
**Trade-off:** No Python needed, works everywhere

## Reducing Standalone Startup Time

### Tried Optimization: Lazy Imports

We can reduce imports to only load modules when needed:

```python
# Before: Load everything at startup
import numpy
import matplotlib
import tecplot

# After: Load only when used
def plot_command():
    import matplotlib  # Only load when plotting
    ...
```

**Potential savings:** 0.2-0.5 seconds (not significant)

### PyInstaller Options

Current build already uses optimal settings:
- `--onefile`: Single executable (convenient but slower)
- `--strip`: Remove debug symbols
- `--noupx`: No compression (faster startup)

Alternative:
- `--onedir`: Multiple files (0.5s faster, but messy)

### Alternative: Nuitka

Nuitka compiles Python to C and can be faster:

```bash
pip install nuitka
nuitka --standalone --onefile main.py
```

**Potential improvement:** 30-50% faster (~1.8s instead of 2.8s)  
**Trade-off:** Complex build, larger file size

## Recommendation

### For You (Developer)

**Use source directly** with this setup:

```bash
# One-time setup
echo 'alias flexflow="conda activate tecplot312 && python /media/arunperiyal/Works/projects/flexflow_manager/main.py"' >> ~/.bashrc
source ~/.bashrc

# Or use the fast wrapper
sudo ln -s /media/arunperiyal/Works/projects/flexflow_manager/flexflow_fast.sh /usr/local/bin/flexflow-dev
```

**Result:** 
- ⚡ 0.4-0.75s startup time
- ✅ Full functionality
- ✅ Easy to debug and modify code

### For Distribution

**Keep the standalone** for:
- End users who don't have Python
- Production environments
- Systems where you can't install conda

The 2.8s startup is acceptable for:
- Batch processing (one startup, many operations)
- Long-running analyses
- Infrequent use

## Comparison Table

| Aspect | Source | Fast Wrapper | Standalone |
|--------|--------|--------------|------------|
| **Startup** | 0.4s | 0.75s | 2.8s |
| **Setup** | conda env | conda env | none |
| **Size** | small | small | 71 MB |
| **Portability** | low | low | high |
| **Best for** | Development | Daily use | Distribution |

## Implementation Guide

### Setup Fast Development Environment

```bash
# 1. Add alias to ~/.bashrc
cat >> ~/.bashrc << 'EOF'

# FlexFlow fast version (source)
alias flexflow-dev='cd /media/arunperiyal/Works/projects/flexflow_manager && conda activate tecplot312 && python main.py'
alias ff='flexflow-dev'  # Even shorter!
EOF

# 2. Reload shell
source ~/.bashrc

# 3. Use it
ff --version              # 0.4s
ff case show CS4SG1U1     # 0.4s
```

### Keep Both Versions

```bash
# Fast version for daily use
flexflow-dev --version    # 0.4s (source)

# Standalone for testing distribution
flexflow --version        # 2.8s (standalone)
```

## Conclusion

The 2.8s startup time of the standalone executable is:

✅ **Normal** for PyInstaller one-file mode  
✅ **Acceptable** for distribution purposes  
❌ **Not ideal** for interactive development

**Solution:** Use source version for development (7x faster), keep standalone for distribution.

---

**Startup Time Comparison:**
- Source: 0.4s ⚡⚡⚡
- Fast wrapper: 0.75s ⚡⚡
- Standalone: 2.8s ⚡

**Recommendation:** Use source for development, standalone for distribution.
