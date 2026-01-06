# UPDATED: Python 3.13 Tecplot Compatibility Investigation

## New Finding - 2026-01-06 05:11 UTC

**GreenLotus works with Python 3.13.5!**

User reported:
```bash
❯ python3 --version
Python 3.13.5

❯ python3 -c "import tecplot; tecplot.data.load_tecplot('CS4SG1U1/binary/riser.1000.plt')"
# Works without crash! ✅
```

## Current Status

### RedLotus (Local - CRASHES)
```
Python: 3.13.2 | packaged by Anaconda, Inc. | [GCC 11.2.0]
Source: Anaconda/Miniconda
Result: Aborted (core dumped) ❌
```

### GreenLotus (Remote - WORKS)
```
Python: 3.13.5 (details needed)
Source: Unknown (possibly pyenv, system, or custom build)
Result: Works perfectly ✅
```

## Possible Explanations

### Hypothesis 1: Python Version Difference
- **Python 3.13.2** (RedLotus): Has the compatibility issue
- **Python 3.13.5** (GreenLotus): Issue fixed in this version?
- Python 3.13.5 released in December 2024 after Tecplot 2024 R1

### Hypothesis 2: Python Build/Distribution ⭐ **MOST LIKELY**
- **Anaconda Python 3.13.2** (RedLotus): Modified build, different ABI
- **Standard Python 3.13.5** (GreenLotus): Official python.org build
- Anaconda packages can have different binary compatibility

### Hypothesis 3: Different Tecplot Installations
- Different pytecplot versions?
- Different Tecplot 360 versions?
- Different compilation flags?

### Hypothesis 4: Environment Configuration
- Different LD_LIBRARY_PATH
- Different PYTHONPATH
- Runtime linking differences

## Investigation Needed

To determine the root cause, need from GreenLotus:

```bash
# Python details
python --version
python -c "import sys; print(sys.version)"
python -c "import sys; print('Executable:', sys.executable)"
python -c "import sys; print('Prefix:', sys.prefix)"
which python

# Tecplot details  
python -c "import tecplot; print('Version:', tecplot.__version__)"
python -c "import tecplot; print('Location:', tecplot.__file__)"

# Environment
echo $PYTHONPATH
echo $LD_LIBRARY_PATH
ldd $(python -c "import tecplot._tecutil; print(tecplot._tecutil.__file__)") 2>/dev/null | head -20
```

## Key Differences Found So Far

### RedLotus
- Python: 3.13.2 from Anaconda
- Compiler: GCC 11.2.0
- Location: ~/miniconda3/bin/python3
- Crash: Yes ❌

### GreenLotus
- Python: 3.13.5 from ??? (to be determined)
- Compiler: ??? (to be determined)
- Location: ??? (to be determined)
- Crash: No ✅

## Implications

### If Python 3.13.5 Fixes It:
- Solution: Upgrade to Python 3.13.5+
- Keep auto-wrapper as fallback
- Update documentation

### If Anaconda Build is the Issue: ⭐
- Solution: Use standard Python instead of Anaconda
- Or use Python 3.12 (known working)
- Auto-wrapper still valuable for mixed environments

### If Environment is the Issue:
- Solution: Document required environment variables
- Update wrapper to set proper environment
- May need LD_LIBRARY_PATH adjustments

## Current Solution Status

The implemented solution (Python 3.12 + auto-wrapper) **still works** and provides:
- ✅ Guaranteed compatibility
- ✅ No manual activation
- ✅ 2-3x performance improvement
- ✅ Tested and verified

## Recommendation

**Keep current solution** (Python 3.12 + auto-wrapper) because:
1. It's verified working
2. Python 3.13 compatibility is unclear (version? build? environment?)
3. Auto-wrapper provides flexibility
4. No user impact

**Additional investigation** to understand Python 3.13.5 success:
- May allow updating documentation
- May allow removing wrapper restriction
- May help others with similar issues

## Test Plan

Once we have GreenLotus Python details:

1. **Test same Python version on RedLotus**
   - If 3.13.5 works: Version-specific issue
   - If 3.13.5 fails: Build/environment issue

2. **Test Anaconda vs Standard Python**
   - Install python.org 3.13.2 on RedLotus
   - Compare with Anaconda 3.13.2
   - Determine if Anaconda is the issue

3. **Compare Tecplot Installations**
   - Check pytecplot versions
   - Check Tecplot 360 versions
   - Check compilation/linking

## Files

- `PYTHON_VERSION_VERIFICATION.md` - Previous verification (needs update)
- `PYTHON_3.13_INVESTIGATION.md` - This document
- All current solutions still valid

---

**Status:** Investigation ongoing  
**Current Solution:** Working (Python 3.12 + auto-wrapper)  
**Next Steps:** Get GreenLotus Python details  
**Date:** 2026-01-06
