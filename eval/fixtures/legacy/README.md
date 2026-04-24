# Legacy hand-labeled examples

These four JSON files are **not** part of the default `eval/fixtures/*.json` run (the harness only loads `*.json` in the **parent** directory).

Use them as **rubric** examples when producing real hand labels or when testing **non-mock** LLM behavior. The **main** fixture set in the parent directory is **100 mock-aligned** synthetic PRs for reproducible CI metrics under `LLM_MOCK_MODE` (see `eval/scripts/generate_synthetic_fixtures.py`).
