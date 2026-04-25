# Legacy fixture examples

These four JSON files are **not** part of the default `eval/fixtures/*.json` CI glob in the **parent** directory (the harness loads `pr_*.json` siblings only).

Use them as **rubric** examples when hand-labeling or when testing **non-mock** LLM behavior. The **main** fixture set in the parent directory is **98** realistic-style PRs from `eval/scripts/generate_realistic_fixtures.py`. For the older **mock-anchor** bundle used to align ground truth to the stub LLM, see `eval/scripts/generate_synthetic_fixtures.py` (optional; not the default CI dataset).
