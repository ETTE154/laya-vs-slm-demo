"""Launch the installed demo without activating a shell environment."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PY = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

if __name__ == "__main__":
    if not PY.exists():
        raise SystemExit("Environment missing. First run: python setup_demo.py")
    raise SystemExit(subprocess.call([str(PY), str(ROOT / "demo/server.py"), *sys.argv[1:]], cwd=ROOT / "demo"))
