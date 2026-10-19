"""Download public pinned model files; validate every file against models.lock.json."""
from pathlib import Path
import argparse
import hashlib
import http.client
import json
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent


def specifications():
    return json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))["models"]


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            result.update(block)
    return result.hexdigest()


def verified(path, spec):
    return path.is_file() and path.stat().st_size == spec["bytes"] and digest(path) == spec["sha256"]


def fetch_file(model, name, spec):
    destination = ROOT / model["directory"] / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if verified(destination, spec):
            print("Verified:", destination.relative_to(ROOT), flush=True)
            return
        raise RuntimeError(f"Existing file has the wrong hash: {destination}. Move it aside before downloading again.")
    url = f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{name}"
    partial = destination.with_name(destination.name + ".part")
    for attempt in range(3):
        try:
            offset = partial.stat().st_size if partial.exists() else 0
            if offset > spec["bytes"]:
                raise RuntimeError(f"Oversized partial file: {partial}. Move it aside and retry.")
            if offset == spec["bytes"]:
                if verified(partial, spec):
                    partial.replace(destination)
                    return
                raise RuntimeError(f"Completed partial file has the wrong hash: {partial}. Move it aside and retry.")
            request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
            print("Downloading:", model["repo"], name, f"({offset}/{spec['bytes']} bytes)", flush=True)
            with urllib.request.urlopen(request, timeout=120) as response:
                append = offset > 0 and response.status == 206
                if append and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                    raise RuntimeError("Unexpected download range; refusing to append mismatched data")
                received = offset if append else 0
                reported = received
                with partial.open("ab" if append else "wb") as handle:
                    while block := response.read(1024 * 1024):
                        handle.write(block)
                        received += len(block)
                        if received > spec["bytes"]:
                            raise RuntimeError("Download exceeds the pinned file size")
                        if received - reported >= 256 * 1024 * 1024:
                            print(name, f"{received / 1024**3:.2f}/{spec['bytes'] / 1024**3:.2f} GiB", flush=True)
                            reported = received
            if not verified(partial, spec):
                raise RuntimeError(f"Size/SHA-256 mismatch: {partial}. Move the partial file aside before retrying.")
            partial.replace(destination)
            print("Verified:", destination.relative_to(ROOT), flush=True)
            return
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead) as exc:
            if attempt == 2:
                raise RuntimeError(f"Download failed: {url}. Check connectivity/proxy and retry; revisions remain pinned.") from exc
            time.sleep(2 ** attempt)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Check hashes without network or downloads")
    parser.add_argument("--model", choices=["laya", "llama1b", "llama3b"], help="Only download/check one model")
    args = parser.parse_args(argv)
    models = specifications()
    if args.model:
        models = {args.model: models[args.model]}
    missing = []
    for key, model in models.items():
        for name, spec in model["files"].items():
            path = ROOT / model["directory"] / name
            if args.verify_only:
                if not verified(path, spec):
                    missing.append(str(path.relative_to(ROOT)))
            else:
                fetch_file(model, name, spec)
    if missing:
        raise SystemExit("Missing or mismatched model files:\n" + "\n".join(missing))
    print("All selected model files match pinned SHA-256 values.", flush=True)


if __name__ == "__main__":
    main()
