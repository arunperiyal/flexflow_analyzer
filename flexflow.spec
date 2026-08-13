# -*- mode: python ; coding: utf-8 -*-
# FlexFlow PyInstaller Specification File
# This creates a standalone executable with embedded Python 3.12

import os
import sys

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Get absolute paths
project_root = os.path.dirname(os.path.abspath(SPEC))

# pyvista/vtk (field render) and meshio (field convert) ship data + many submodules;
# let PyInstaller collect them. vtk is large -- the frozen build will grow.
_extra_datas, _extra_binaries, _extra_hidden = [], [], []
for _pkg in ('pyvista', 'vtkmodules', 'meshio'):
    try:
        _d, _b, _h = collect_all(_pkg)
        _extra_datas += _d
        _extra_binaries += _b
        _extra_hidden += _h
    except Exception:
        pass  # not installed in this build env -- field render/convert will be unavailable

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=_extra_binaries,
    datas=[
        ('src', 'src'),
        ('README.md', '.'),
    ] + _extra_datas,
    hiddenimports=[
        'numpy',
        'matplotlib',
        'matplotlib.backends.backend_agg',
        'pandas',
        'yaml',
        'rich',
        'tqdm',
        'markdown',
        'meshio',
        'pyvista',
        'src',
        'src.cli',
        'src.cli.registry',
        'src.cli.help_messages',
        'src.utils',
        'src.utils.colors',
        'src.utils.logger',
        'src.core',
        'src.core.case',
        'src.core.readers',
        'src.commands',
        'src.commands.base',
        'src.commands.field',
        'src.installer',
        'src.plt',
        'src.plt.fxplt',
        'src.plt.convert',
        'src.plt.camera',
        'src.plt.render',
    ] + _extra_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove unnecessary files to reduce size
a.datas = [x for x in a.datas if not x[0].startswith('matplotlib/tests/')]
a.datas = [x for x in a.datas if not x[0].startswith('numpy/tests/')]

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
    strip=True,
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
