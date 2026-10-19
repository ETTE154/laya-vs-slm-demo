"""Install into this repository's .venv; never start a model or alter global Python."""
from pathlib import Path
import argparse
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".venv"
PY = ENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(args):
    environment = os.environ.copy()
    environment.setdefault("PIP_CACHE_DIR", str(ROOT / ".cache/pip"))
    subprocess.run([str(value) for value in args], cwd=ROOT, env=environment, check=True)


def check_runtime():
    if not PY.exists():
        raise SystemExit("Missing .venv. Run: python setup_demo.py")
    script = """import importlib.metadata,json
expected={'laya':'0.4.11','torch':'2.14.1','transformers':'5.20.1','tokenizers':'0.23.3','safetensors':'0.8.0','huggingface_hub':'2.2.0','numpy':'2.5.4'}
actual={key:importlib.metadata.version(key) for key in expected}
print(json.dumps(actual,indent=2))
assert all(actual[k].split('+')[0]==v for k,v in expected.items()), 'Runtime versions differ from requirements.txt'
import laya,torch,transformers
assert not torch.cuda.is_initialized(), 'Setup must not initialize CUDA'
"""
    run([PY, "-c", script])
    run([PY, "-m", "pip", "check"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-models", action="store_true", help="Install/check packages only; no large model downloads")
    parser.add_argument("--check", action="store_true", help="Verify the existing runtime and model hashes; no installation")
    parser.add_argument("--offline", action="store_true", help="Only verify an already installed environment and local model files")
    args = parser.parse_args(argv)
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Use Python 3.12. Windows: py -3.12 setup_demo.py; Linux/macOS: python3.12 setup_demo.py")
    if not args.check and not args.offline:
        print(f"Project: {ROOT}\nFree disk: {shutil.disk_usage(ROOT).free / 1024**3:.1f} GiB", flush=True)
        if not PY.exists():
            venv.create(ENV, with_pip=True)
        run([PY, "-m", "pip", "install", "--upgrade", "pip"])
        # On Windows/Linux the official CPU wheel avoids installing CUDA libraries.
        torch_args = [PY, "-m", "pip", "install", "torch==2.14.1"]
        if platform.system() in ("Windows", "Linux"):
            torch_args += ["--index-url", "https://download.pytorch.org/whl/cpu"]
        run(torch_args)
        run([PY, "-m", "pip", "install", "-r", ROOT / "requirements.txt"])
    check_runtime()
    if not args.skip_models:
        model_args = [PY, ROOT / "download_models.py"]
        if args.check or args.offline:
            model_args.append("--verify-only")
        run(model_args)
    print("Setup verified. Start with: python run_demo.py --open", flush=True)


if __name__ == "__main__":
    main()
