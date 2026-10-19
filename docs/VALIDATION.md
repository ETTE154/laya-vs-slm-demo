# Installation and reproduction validation

Validated on 2026-10-19 with Windows 11, Python 3.12, Intel Core i9-10900K, CPU inference, FP32, 8 threads. These are implementation checks, not an accuracy guarantee.

| Check | Result |
|---|---|
| New project-local virtual environment | Created from scratch using setup_demo.py |
| Dependency installation | Downloaded from official PyTorch CPU index and PyPI; core pins installed successfully |
| Import/version checks and pip check | PASS; torch 2.14.1+cpu, laya 0.4.11, transformers 5.20.1 |
| Pinned model URLs | Actually downloaded config.json from each of the three pinned public repositories and verified SHA-256 |
| All model files | Verified size and SHA-256 for all 21 files in models.lock.json |
| Large weights during this validation | Reused existing matching files locally rather than downloading 9.7GB again; no weights committed |
| Shared-task and streaming unit tests | 19 PASS |
| Downloader tests | 7 PASS, covering corruption, atomic publication, cache reuse, Range resume and ignored Range |
| Actual exported application | Started on a separate localhost port with the newly installed environment |
| Math/general/robot inference | All nine model calls completed; streaming text, common task hashes, order, and token counts checked |
| Behavior after export/path cleanup | Actual output text and generated token counts matched the original application on all nine calls |

Full measured outputs are in [clean_install_live.json](../reference_results/clean_install_live.json). The installer generated no model replacements, candidate generation, answer overrides or task-specific prompt tuning.

Observed model results include wrong answers and SLM formatting violations. For the arithmetic example `2+3?` with A=4, B=5, C=6, D=7, this snapshot returned Laya `A`, 1B `C. 6` (format violation), and 3B `A`. A successful reproduction means preserving and reporting those outcomes, not relabeling them as correct.

Windows is the actually tested platform for this installation snapshot. Linux/macOS entry points are provided but were not run on this host. Time measurements vary by hardware and load. No real robot or Jev API was used.
