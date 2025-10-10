# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


def _resolve_spec_dir() -> Path:
    """Return the directory that contains this spec file.

    PyInstaller executes spec files via ``exec`` and, depending on the
    invocation path, ``__file__`` may not be injected into the globals.  When
    that happens the previous implementation crashed before the build even
    started.  Fall back to the current working directory so the build can
    continue, which matches PyInstaller's default behaviour when running a
    ``.spec`` from the command line.
    """

    spec_path = globals().get("__file__")
    if spec_path:
        return Path(spec_path).resolve().parent
    return Path.cwd()

from PyInstaller.utils.hooks import collect_all

block_cipher = None

SPEC_DIR = _resolve_spec_dir()
ICON_SOURCE = SPEC_DIR / "Kiroshi_Logo.png"
ICON_TARGET = SPEC_DIR / "Kiroshi_Logo.ico"


def _ensure_icon(source: Path, target: Path) -> Path:
    """Generate a Windows .ico file from the project PNG if needed."""

    if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
        return target

    from PIL import Image
    image = Image.open(source)
    image.save(
        target,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)],
    )
    return target


ICON_PATH = _ensure_icon(ICON_SOURCE, ICON_TARGET)


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
    icon=str(ICON_PATH),
    uac_admin=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
