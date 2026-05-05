"""Entry point: python run.py  (or double-click cost_control.exe)"""
import os
import socket
import sys
import threading
import time
import urllib.request


def _abort_if_stale() -> None:
    """When running as a frozen exe, compare on-disk source against the hash
    embedded at build time.  Abort with clear rebuild instructions if they differ.

    Skipped entirely when running from source (python run.py) so developers
    always get live code with no friction.
    """
    if not getattr(sys, "frozen", False):
        return  # running from source — always current, nothing to check

    import hashlib
    import pathlib

    exe_dir = pathlib.Path(sys.executable).parent
    src_dir = exe_dir / "costcontrol"

    if not src_dir.exists():
        return  # portable install without source alongside — skip

    # Hash every .py file in costcontrol/ (same algorithm used in the spec)
    h = hashlib.sha256()
    for p in sorted(src_dir.rglob("*.py")):
        h.update(p.read_bytes())
    disk_hash = h.hexdigest()

    # Read the hash that was baked in at build time
    try:
        build_hash = (pathlib.Path(sys._MEIPASS) / "source_hash.txt").read_text().strip()
    except Exception:
        return  # hash file absent (old build) — skip silently

    if disk_hash == build_hash:
        return  # hashes match — exe is current

    print()
    print("=" * 60)
    print("  STALE BUILD — SERVER NOT STARTED")
    print()
    print("  Source files in costcontrol/ have been modified since")
    print("  cost_control.exe was last built.  Starting now would")
    print("  run outdated code and changes would have no effect.")
    print()
    print("  Rebuild the executable (close any running server first):")
    print()
    print("    cd app")
    print("    python -m PyInstaller --clean --distpath . cost_control.spec")
    print()
    print("  Or run directly from source without rebuilding:")
    print()
    print("    python run.py")
    print("=" * 60)
    print()
    input("  Press Enter to close this window...")
    sys.exit(1)


_abort_if_stale()

import uvicorn


def _find_free_port(start: int = 8090) -> int:
    """Return the first free TCP port starting from *start*.

    Prints a warning for every skipped port so stale server processes
    are immediately visible.
    """
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                print(f"  [!] Port {port} already in use — is an old server still running?")
    return start  # fall through; uvicorn will surface the error


def _open_browser(url: str) -> None:
    """Poll until the server responds, then open the default browser."""
    for _ in range(60):          # wait up to ~60 seconds
        time.sleep(1)
        try:
            urllib.request.urlopen(url, timeout=1)
            break
        except Exception:
            continue
    # os.startfile is the most reliable way to open a URL in the
    # Windows default browser from a frozen executable.
    os.startfile(url)


if __name__ == "__main__":
    from costcontrol.app import app

    port = _find_free_port(8090)
    url = f"http://127.0.0.1:{port}"

    print("=" * 50)
    print("  Cost Control MVP")
    print(f"  Address : {url}")
    print("  Browser will open automatically.")
    print("  Close this window to stop the server.")
    print("=" * 50 + "\n")

    threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    try:
        uvicorn.run(app, host="127.0.0.1", port=port, reload=False, log_level="info")
    except Exception as exc:
        print(f"\n  ERROR: {exc}")
    finally:
        print(f"\n  Server stopped.")
        print(f"  If the page didn't load, open manually: {url}")
        input("\n  Press Enter to close this window...")
