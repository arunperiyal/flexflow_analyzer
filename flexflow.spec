# -*- mode: python ; coding: utf-8 -*-
# FlexFlow PyInstaller Specification File
# This creates a standalone executable with embedded Python 3.12

import os
import sys

block_cipher = None

# Get absolute paths
project_root = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=[
        ('src', 'src'),
        ('README.md', '.'),
    ],
    hiddenimports=[
        'numpy',
        'matplotlib',
        'matplotlib.backends.backend_agg',
        'tecplot',
        'tecplot.data',
        'tecplot.tecutil',
        'pandas',
        'yaml',
        'rich',
        'tqdm',
        'markdown',
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
        'src.core.parsers',
        'src.commands',
        'src.commands.base',
        'src.commands.plot',
        'src.commands.compare',
        'src.commands.case_group',
        'src.commands.tecplot_cmd',
        'src.installer',
        'src.tecplot_handler',
        'src.tecplot_pytec',
    ],
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
