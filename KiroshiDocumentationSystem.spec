# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = [
    ('case_documentation_app.py', '.'),
    ('aatom_chat.py', '.'),
    ('doom_game.py', '.'),
    ('atom_logo.png', '.'),
    ('Kiroshi_Logo.png', '.'),
    ('atom_memory.json', '.'),
    ('manual_memory.json', '.'),
    ('docs/kiroshi_quick_reference.json', 'docs'),
    ('.streamlit/config.toml', '.streamlit'),
]
binaries = []
hiddenimports = ['aatom_chat']
tmp_ret = collect_all('streamlit')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# ReportLab ships fonts, ICC profiles, and other assets that PyInstaller does
# not automatically discover when only collecting Python modules.  Pull in the
# package resources so that the PDF export feature keeps working in the bundled
# executable.
tmp_ret = collect_all('reportlab')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['run_app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='KiroshiDocumentationSystem',
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
