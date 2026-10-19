# Reproduce this demo

Read README.md before installing. The user can delegate setup by providing this repository URL; the documented installation, public pinned model downloads and localhost execution are the intended workflow.

## Execution order

1. Inspect the host and use 64-bit Python 3.12. Do not install into global Python.
2. Run `python setup_demo.py` from the repository root with the Python 3.12 executable (`py -3.12` on Windows or `python3.12` on POSIX).
3. Run `python setup_demo.py --check` and both stdlib test suites in README. Use this repository's `.venv` interpreter for tests.
4. Launch `python run_demo.py --open`, or omit `--open` for a headless session. Bind only to 127.0.0.1. Do not kill an unknown process on 8776; use `--port` if occupied.
5. Check `/api/meta` for `app=local-comparison-v3` and `task_mode=shared_multiple_choice`. On first inference all three models load sequentially.
6. Run `verify_live.py` or the math/general/robot examples. Verify streaming before completion, common task hashes, order and Laya's zero generated tokens. Report model wrong answers and format violations honestly.
7. Report installation results, actual URL/port, test results, hardware limitations and any blocking download errors. Do not say setup or inference succeeded based only on a running HTTP server.

## Constraints

- Preserve model revisions and file hashes in `models.lock.json`, runtime pins, fixed common instruction, and user-provided candidates. Do not silently swap a checkpoint or tune prompts to make demo examples pass.
- Current tasks are shared multiple-choice answer selection. Do not restore the old robot-only labels or generate candidates with another model.
- The live app and its tests are `demo/`. No historical benchmark code is required. `reference_results/` are past measured records, not the output of the current machine.
- Setup needs about 9.7GB of model downloads, project-local packages/cache, and preferably at least 32GB RAM. If resources are insufficient, explain the limitation before starting an unworkable inference run.
- Respect model licenses in LICENSES/. No auth bypasses, certificate validation disabling, secrets committed to git, model weights or `.venv` uploads.
- Runtime is intentionally offline CPU/FP32/8 threads/batch1. A GPU/quantization/model change is a separate configuration and cannot be represented as the recorded baseline.
- Keep outputs and test logs under `test-results/` (gitignored). On interrupted downloads rerun the same installer; it verifies completed files and resumes supported partial downloads.
- Do not deploy publicly or connect real robot hardware as part of reproduction.
