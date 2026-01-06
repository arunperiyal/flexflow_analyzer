# FlexFlow Standalone Distribution - Implementation Plan

## Goal
Create a standalone FlexFlow executable that works on any system without Python dependency conflicts.

## Recommended Approach: PyInstaller + Bundled Python

### Why This Works Best:
1. ✅ Single executable file
2. ✅ Bundles known-working Python (3.12)
3. ✅ All dependencies included
4. ✅ No system Python conflicts
5. ✅ Easy for users - just download and run

### Architecture

```
flexflow (standalone executable)
├── Embedded Python 3.12 interpreter
├── All Python dependencies (numpy, matplotlib, etc.)
├── FlexFlow code
├── PyTecplot client library
└── Auto-detects Tecplot 360 installation
```

## Implementation Steps

### Step 1: Prepare Build Environment

```bash
# Use Python 3.12 (known working version)
conda create -n flexflow_build python=3.12 -y
conda activate flexflow_build

# Install PyInstaller
pip install pyinstaller

# Install all FlexFlow dependencies
pip install numpy matplotlib pyyaml markdown rich tqdm pandas pytecplot
```

### Step 2: Create PyInstaller Spec File

```python
# flexflow.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['/media/arunperiyal/Works/projects/flexflow_manager'],
    binaries=[],
    datas=[
        ('module', 'module'),
        ('docs', 'docs'),
    ],
    hiddenimports=[
        'numpy',
        'matplotlib',
        'tecplot',
        'pandas',
        'yaml',
        'rich',
        'tqdm',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='flexflow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

### Step 3: Build Standalone Executable

```bash
# Build single-file executable
pyinstaller flexflow.spec --onefile

# Result: dist/flexflow (single executable, ~80-100 MB)
```

### Step 4: Test Standalone Binary

```bash
# Test on system WITHOUT Python 3.12
./dist/flexflow --version
./dist/flexflow case show CS4SG1U1
./dist/flexflow field info CS4SG1U1  # Uses embedded Python 3.12!
```

### Step 5: Distribution

```bash
# Create release package
tar -czf flexflow-standalone-v2.0-linux-x86_64.tar.gz \
    dist/flexflow \
    README.md \
    PYTECPLOT_GUIDE.md

# Users just extract and run:
# ./flexflow <command>
```

## Advantages

### For Users:
- ✅ **No Python installation needed**
- ✅ **No environment activation**
- ✅ **No version conflicts**
- ✅ **Just download and run**
- ✅ **Works with system Python 3.13, doesn't matter!**

### For Developers:
- ✅ **Known working Python version**
- ✅ **Reproducible builds**
- ✅ **Easy distribution**
- ✅ **Single file to maintain**

## Size Optimization

### Techniques to Reduce Size:

1. **Exclude unnecessary modules:**
```python
excludes=['tkinter', 'test', 'unittest']
```

2. **Use UPX compression:**
```bash
pyinstaller --onefile --upx-dir=/usr/bin main.py
```

3. **Strip debug symbols:**
```bash
strip dist/flexflow
```

**Final size: ~50-80 MB** (acceptable for a complete application)

## Alternative: AppImage (Linux-specific)

More polished Linux integration:

```bash
# Create AppImage structure
mkdir -p flexflow.AppDir/usr/bin
mkdir -p flexflow.AppDir/usr/lib

# Copy standalone binary
cp dist/flexflow flexflow.AppDir/usr/bin/

# Create desktop integration
cat > flexflow.AppDir/flexflow.desktop << EOF
[Desktop Entry]
Name=FlexFlow
Exec=flexflow
Icon=flexflow
Type=Application
Categories=Science;Engineering;
EOF

# Build AppImage
appimagetool flexflow.AppDir flexflow-x86_64.AppImage

# Result: Single-click runnable application
./flexflow-x86_64.AppImage case show CS4SG1U1
```

## Docker Alternative (For Server Deployments)

```dockerfile
# Dockerfile
FROM python:3.12-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Copy FlexFlow
COPY . /app
WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Entrypoint
ENTRYPOINT ["python", "main.py"]

# Usage:
# docker run -v $PWD:/data flexflow case show CS4SG1U1
```

## Comparison Matrix

| Approach | Size | Setup | Python Independent | Distribution |
|----------|------|-------|-------------------|--------------|
| **PyInstaller** | 80 MB | None | ✅ Yes | ⭐⭐⭐⭐⭐ |
| **AppImage** | 85 MB | None | ✅ Yes | ⭐⭐⭐⭐ |
| **Docker** | 200 MB | Docker | ✅ Yes | ⭐⭐⭐ |
| **Current (wrapper)** | Small | conda | ❌ No | ⭐⭐ |

## Recommendation

**Use PyInstaller** for the best balance of:
- User convenience
- Distribution simplicity
- Python independence
- Reasonable file size

## Next Steps

1. Test PyInstaller build with current codebase
2. Optimize for size
3. Test on multiple systems
4. Create release package
5. Update documentation

---

**Result:** Users download `flexflow` binary, run it directly, no Python concerns!

Would you like me to create the PyInstaller build now?
