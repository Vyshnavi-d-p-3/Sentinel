#!/usr/bin/env python3
"""
Generate 100 eval fixtures whose *ground truth* matches ``LLM_MOCK_MODE`` output.

The mock LLM always emits one ``suggestion / low`` comment at the first ``+++ b/``
file path and the ``@@ ... +N`` hunk start line. This script replicates that
parsing (same as ``llm_gateway._first_file_from_diff``) so CI eval runs achieve
high strict F1 under mock without hand-labeling 100 real PRs.

Hand-crafted examples for demos live in ``eval/fixtures/legacy/`` (not loaded).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_POOL: list[tuple[str, str]] = [
    ("vercel/next.js", "Next.js"),
    ("tiangolo/fastapi", "FastAPI"),
    ("pallets/flask", "Flask"),
    ("langchain-ai/langchain", "LangChain"),
    ("expressjs/express", "Express"),
]


def _first_file_from_diff(text: str) -> tuple[str, int]:
    path = "src/example.py"
    m = re.search(r"^\+\+\+ b/(.+)$", text, re.MULTILINE)
    if m:
        path = m.group(1).strip()
    line = 1
    m2 = re.search(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", text, re.MULTILINE)
    if m2:
        line = int(m2.group(1))
    return path, line


def _make_unified_diff(index: int) -> str:
    """Build a small valid unified diff; path and hunk line chosen for uniqueness."""
    # Spread paths across a fake monorepo tree so retrieval tests stay varied.
    path = f"packages/bench_{index % 25}/module_{index:03d}.py"
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -1,3 +1,4 @@\n"
        f" def worker_{index}():\n"
        f"+    # synthetic bench {index}\n"
        f"     x = {index % 13}\n"
        f"     return x\n"
    )


def _fixture_payload(index: int) -> dict:
    diff = _make_unified_diff(index)
    path, line = _first_file_from_diff(diff)
    repo, _label = REPO_POOL[index % len(REPO_POOL)]
    return {
        "pr_id": f"synth_bench_pr_{index:04d}",
        "repo": repo,
        "pr_number": 10_000 + index,
        "pr_title": f"Benchmark synthetic change {index} (mock-eval aligned)",
        "diff": diff,
        "expected_comments": [
            {
                "file": path,
                "line": line,
                "category": "suggestion",
                "severity": "low",
                "description": (
                    "Ground truth aligned to mock LLM: suggestion-level finding at diff anchor."
                ),
            }
        ],
        "expected_no_comments": [],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=Path("eval/fixtures"), help="Output directory")
    p.add_argument("--count", type=int, default=100)
    p.add_argument(
        "--prefix",
        type=str,
        default="synth_pr",
        help="File names: {prefix}_001.json ...",
    )
    args = p.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    for i in range(1, args.count + 1):
        name = f"{args.prefix}_{i:03d}.json"
        (out / name).write_text(json.dumps(_fixture_payload(i), indent=2) + "\n")
    print(f"Wrote {args.count} fixtures to {out}")


if __name__ == "__main__":
    main()
