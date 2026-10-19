"""Record actual math/general/robot runs and verify the shared streaming contract."""
from pathlib import Path
import argparse
import json
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "demo"))
from shared_task import parse_task

CASES = [("math", "B"), ("general", "C"), ("robot", "A")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8776")
    parser.add_argument("--out", type=Path, default=ROOT / "test-results/live.json")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    with urllib.request.urlopen(base + "/api/meta", timeout=10) as response:
        metadata = json.load(response)
    if metadata.get("app") != "local-comparison-v3" or metadata.get("task_mode") != "shared_multiple_choice":
        raise SystemExit("Unexpected server; start this repository's run_demo.py first.")
    reports = []
    for name, expected in CASES:
        text = (ROOT / "examples" / (name + ".txt")).read_text(encoding="utf-8").strip()
        task = parse_task(text)
        request = urllib.request.Request(base + "/api/stream", data=json.dumps({"input": text}).encode("utf-8"), headers={"Content-Type": "application/json"})
        begin = time.perf_counter()
        events = []
        with urllib.request.urlopen(request, timeout=600) as response:
            for line in response:
                event = json.loads(line)
                events.append({"received_ms": round((time.perf_counter() - begin) * 1000, 3), **event})
                if event["type"] in ("model_start", "model_result", "model_error", "error"):
                    print(json.dumps({"case": name, **event}, ensure_ascii=False), flush=True)
        assert events and events[0]["type"] == "run_start" and events[-1]["type"] == "run_end"
        assert events[0]["task"] == task
        assert not [e for e in events if e["type"] in ("error", "model_error")]
        assert [e["model"] for e in events if e["type"] == "model_start"] == ["laya", "llama1b", "llama3b"]
        results = {e["model"]: e for e in events if e["type"] == "model_result"}
        assert list(results) == ["laya", "llama1b", "llama3b"]
        assert all(r["task_sha256"] == task["task_sha256"] for r in results.values())
        assert results["laya"]["output_tokens"] == 0 and results["laya"]["tokens_per_second"] is None
        for key in ("llama1b", "llama3b"):
            chunks = [e for e in events if e["type"] == "token" and e["model"] == key]
            assert "".join(e["text"] for e in chunks) == results[key]["text"]
            assert chunks[-1]["output_tokens"] == results[key]["output_tokens"]
            assert any(e["text"] and e["received_ms"] < results[key]["received_ms"] for e in chunks)
        reports.append({"case": name, "task": task, "expected": expected,
                        "correct": {key: r["valid_choice"] and r["label"] == expected for key, r in results.items()},
                        "results": results, "events": events})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"contract_checks_pass": True, "cases": reports}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Streaming/shared-task checks passed. This does NOT mean the answers are correct.")
    print(json.dumps({r["case"]: r["correct"] for r in reports}, ensure_ascii=False, indent=2))
    print("Saved:", args.out)


if __name__ == "__main__":
    main()
