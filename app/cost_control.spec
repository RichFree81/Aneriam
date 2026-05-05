# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Cost Control MVP single-file executable.
Build with:  python -m PyInstaller --clean --distpath . cost_control.spec
Output:      cost_control.exe  (in the same folder as this spec file)
"""
import hashlib
from pathlib import Path

ROOT = Path(SPECPATH)

# ---------------------------------------------------------------------------
# Compute a hash of every .py file in costcontrol/ and embed it in the exe.
# run.py reads this hash at startup and aborts if on-disk source has drifted.
# ---------------------------------------------------------------------------
def _compute_source_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted((root / "costcontrol").rglob("*.py")):
        h.update(p.read_bytes())
    return h.hexdigest()

_hash_dir = ROOT / "build"
_hash_dir.mkdir(exist_ok=True)
_hash_file = _hash_dir / "source_hash.txt"
_hash_file.write_text(_compute_source_hash(ROOT))

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Embed the source hash so run.py can detect stale builds at startup.
        (str(_hash_file), "."),
        # Templates are loaded from disk at runtime (APP_DIR/templates/).
        # Do NOT bundle them here — keeping them on disk means template changes
        # take effect immediately without rebuilding the exe.
    ],
    hiddenimports=[
        # FastAPI / Starlette internals that PyInstaller may miss
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "anyio",
        "anyio._backends._asyncio",
        # SQLAlchemy dialects
        "sqlalchemy.dialects.sqlite",
        # lxml
        "lxml",
        "lxml.etree",
        # Email-validator (fastapi optional dep)
        "email_validator",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "PIL",
        "IPython",
        "jupyter",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="cost_control",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # keep console so the user can see server logs
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
