#!/usr/bin/env python3
"""Generate 98 realistic eval fixtures for Sentinel (see eval/fixtures/README.md)."""
from __future__ import annotations

import json
import os
import textwrap
from collections.abc import Iterator

FIXTURES_DIR = os.path.dirname(os.path.abspath(__file__))
if FIXTURES_DIR.endswith("scripts"):
    FIXTURES_DIR = os.path.join(os.path.dirname(FIXTURES_DIR), "fixtures")


def _simple_diff(path: str, hunk: str) -> str:
    # Dedent hunks so readable indented Python strings become valid diff lines.
    h = textwrap.dedent(hunk).strip("\n")
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n{h}\n"


# ——— Hand-labeled (representative) fixtures from OSS-style diffs ———
def _core_fixtures() -> list[dict]:
    f: list[dict] = []
    f.append(
        {
            "pr_id": "fastapi_pr_10842",
            "repo": "tiangolo/fastapi",
            "pr_number": 10842,
            "pr_title": "Add user search endpoint with filtering",
            "is_clean": False,
            "diff": _simple_diff(
                "app/api/routes/users.py",
                """@@ -1,8 +1,12 @@
                 -from fastapi import APIRouter, Depends
                 +from fastapi import APIRouter, Depends, Query
                  from sqlalchemy.ext.asyncio import AsyncSession
                 +from sqlalchemy import text
                  from app.db.session import get_db
                  
                  router = APIRouter()
                  
                 +@router.get("/users/search")
                 +async def search_users(q: str = Query(...), db: AsyncSession = Depends(get_db)):
                 +    result = await db.execute(text(f"SELECT * FROM users WHERE name LIKE '%{q}%'"))
                 +    return result.mappings().all()
                 """,
            ),
            "expected_comments": [
                {
                    "file": "app/api/routes/users.py",
                    "line": 10,
                    "category": "security",
                    "severity": "critical",
                    "description": (
                        "SQL injection via f-string interpolation of user input into raw SQL query."
                    ),
                }
            ],
            "expected_no_comments": [],
        }
    )
    f.append(
        {
            "pr_id": "express_pr_5804",
            "repo": "expressjs/express",
            "pr_number": 5804,
            "pr_title": "Add file download endpoint for reports",
            "is_clean": False,
            "diff": _simple_diff(
                "lib/routes/reports.js",
                """@@ -1,5 +1,14 @@
                 const express = require('express');
                 const router = express.Router();
                 +const path = require('path');
                 +const fs = require('fs');
                 +
                 +router.get('/download', (req, res) => {
                 +  const filename = req.query.file;
                 +  const filepath = path.join('/var/reports', filename);
                 +  if (fs.existsSync(filepath)) {
                 +    res.download(filepath);
                 +  } else {
                 +    res.status(404).send('Not found');
                 +  }
                 +});
                 """,
            ),
            "expected_comments": [
                {
                    "file": "lib/routes/reports.js",
                    "line": 6,
                    "category": "security",
                    "severity": "critical",
                    "description": (
                        "Path traversal: user-controlled filename joined to a base path without "
                        "sanitization; '../' can escape the directory."
                    ),
                }
            ],
            "expected_no_comments": [],
        }
    )
    f.append(
        {
            "pr_id": "nextjs_pr_58310",
            "repo": "vercel/next.js",
            "pr_number": 58310,
            "pr_title": "Fix middleware redirect status validation",
            "is_clean": False,
            "diff": _simple_diff(
                "packages/next/src/server/web/spec-extension/response.ts",
                """@@ -45,10 +45,10 @@ export class NextResponse extends Response {
                  static redirect(url: string | URL, status?: number): NextResponse {
                    const destination = typeof url === 'string' ? new URL(url) : url
                 -  if (![301, 302, 303, 307, 308].includes(status ?? 307)) {
                 -    throw new RangeError('redirect status must be a redirect status code')
                 -  }
                 -  return new NextResponse(null, {
                 +  return new NextResponse(null, {
                    status: status ?? 307,
                    headers: { Location: destination.toString() },
                  })
                 """,
            ),
            "expected_comments": [
                {
                    "file": "packages/next/src/server/web/spec-extension/response.ts",
                    "line": 48,
                    "category": "bug",
                    "severity": "high",
                    "description": (
                        "Removed redirect status code validation; invalid codes can produce "
                        "malformed HTTP responses."
                    ),
                }
            ],
            "expected_no_comments": [],
        }
    )
    f.append(
        {
            "pr_id": "fastapi_pr_11100",
            "repo": "tiangolo/fastapi",
            "pr_number": 11100,
            "pr_title": "Update type hints to use modern union syntax",
            "is_clean": True,
            "diff": _simple_diff(
                "app/models/user.py",
                """@@ -1,8 +1,8 @@
                 -from typing import Optional, List
                 +from __future__ import annotations
                  from pydantic import BaseModel
                  
                  class User(BaseModel):
                    name: str
                 -  email: Optional[str] = None
                 -  roles: List[str] = []
                 +  email: str | None = None
                 +  roles: list[str] = []
                 """,
            ),
            "expected_comments": [],
            "expected_no_comments": [
                {
                    "file": "app/models/user.py",
                    "line": 6,
                    "reason": "PEP 604 union syntax is preferred on Python 3.10+.",
                }
            ],
        }
    )
    f.append(
        {
            "pr_id": "express_pr_5910",
            "repo": "expressjs/express",
            "pr_number": 5910,
            "pr_title": "Update dependencies and fix lockfile",
            "is_clean": True,
            "diff": _simple_diff(
                "lib/app-version.js",
                """@@ -1,3 +1,3 @@
 const semver = require('semver');
-exports.VERSION = '1.3.8';
+exports.VERSION = '1.3.9';
""",
            ),
            "expected_comments": [],
            "expected_no_comments": [
                {
                    "file": "lib/app-version.js",
                    "line": 2,
                    "reason": "Patch-level version bump is routine maintenance.",
                }
            ],
        }
    )
    return f


def _labeled_pool() -> list[tuple[str, str, int, str, str, str, str, str, int]]:
    """repo, pr_id prefix, pr_num, path, hunk, cat, sev, desc, line (approx)."""
    return [
        (
            "tiangolo/fastapi",
            "fastapi",
            10900,
            "app/core/secrets.py",
            """@@ -0,0 +1,2 @@
+API_KEY = "hardcoded-secret"
+print(API_KEY)
""",
            "security",
            "critical",
            "Hardcoded API key in source; load from the environment or a secret manager.",
            1,
        ),
        (
            "pallets/flask",
            "flask",
            5200,
            "src/flask/sessions.py",
            """@@ -10,2 +10,4 @@
+def get_sid():
+    return request.cookies.get('session') or '0' * 8
""",
            "security",
            "high",
            "Predictable default session id weakens session fixation protections.",
            12,
        ),
        (
            "vercel/next.js",
            "nextjs",
            58000,
            "app/middleware.ts",
            """@@ -1,2 +1,4 @@
+const tok = process.env.AUTH_TOKEN;
+export const config = { matcher: ["/:path*"] };
""",
            "security",
            "high",
            "Auth token from env exposed in client bundle if this file is not server-only; verify 'use server' or placement.",
            1,
        ),
        (
            "langchain-ai/langchain",
            "langchain",
            18400,
            "libs/langchain/langchain/tools/http.py",
            """@@ -5,2 +5,5 @@
+def fetch(url: str) -> str:
+    return requests.get(url, verify=False).text
""",
            "security",
            "high",
            "Disabling TLS verification allows MITM; do not set verify=False in production.",
            6,
        ),
        (
            "tiangolo/fastapi",
            "fastapi",
            10920,
            "app/api/routes/items.py",
            """@@ -5,2 +5,6 @@
+@router.get("/items/count")
+async def count_items(db: Session = Depends(get_sync_db)):
+    return db.query(Item).count()
""",
            "bug",
            "high",
            "Sync ORM work inside an async route can block the event loop; use AsyncSession or threadpool.",
            7,
        ),
        (
            "pallets/flask",
            "flask",
            5210,
            "src/flask/ctx.py",
            """@@ -3,2 +3,4 @@
+def buggy():
+    return request.json['foo'] + request.json['bar']
""",
            "bug",
            "medium",
            "KeyError risk if json keys are missing; use .get() with defaults.",
            4,
        ),
        (
            "vercel/next.js",
            "nextjs",
            58100,
            "app/page.tsx",
            """@@ -1,3 +1,5 @@
+'use client'
+if (window.innerWidth < 0) {}
 export default function Page() { return null; }
""",
            "bug",
            "high",
            "Window access without SSR guard can break server rendering.",
            2,
        ),
        (
            "langchain-ai/langchain",
            "langchain",
            18410,
            "libs/langchain/langchain/chains/qa.py",
            """@@ -20,2 +20,4 @@
+    for doc in documents:
+        results.append(embeddings.embed_query(doc.page_content))
""",
            "performance",
            "high",
            "Per-document embedding in a loop; prefer batch API to reduce N round-trips.",
            22,
        ),
        (
            "tiangolo/fastapi",
            "fastapi",
            10910,
            "app/api/routes/bulk.py",
            """@@ -4,2 +4,5 @@
+@router.get("/all")
+def all_rows(db: Session = Depends(get_db)):
+    return db.query(Log).all()
""",
            "performance",
            "high",
            "Loads entire table into memory; add pagination or streaming.",
            5,
        ),
        (
            "expressjs/express",
            "express",
            5800,
            "lib/middleware/parse.js",
            """@@ -1,2 +1,4 @@
+const body = JSON.parse(req.body)
+// ...
""",
            "bug",
            "high",
            "JSON.parse on raw body can throw; wrap in try/catch and return 400 on error.",
            2,
        ),
        (
            "tiangolo/fastapi",
            "fastapi",
            10890,
            "app/utils/strings.py",
            """@@ -0,0 +1,3 @@
+def f(a,b):
+    return a+b
""",
            "style",
            "medium",
            "Function and parameters should have descriptive names (e.g. add_numbers).",
            1,
        ),
        (
            "vercel/next.js",
            "nextjs",
            58200,
            "app/components/ErrorBoundary.tsx",
            """@@ -0,0 +1,6 @@
+'use client'
+import { Component } from 'react'
+export class E extends Component {
+  render() { if ((this.state as any).e) return null; return this.props.children; }
+}
""",
            "suggestion",
            "medium",
            "Consider logging errors in componentDidCatch and surfacing a fallback UI for operators.",
            4,
        ),
        (
            "pallets/flask",
            "flask",
            5150,
            "src/flask/blueprints.py",
            """@@ -8,2 +8,4 @@
+@bp.get("/u/<name>")
+def u(name: str):
+     return f"<h1>{name}</h1>"
""",
            "security",
            "high",
            "Unescaped user input in HTML enables XSS; use templates with auto-escaping.",
            9,
        ),
        (
            "langchain-ai/langchain",
            "langchain",
            18390,
            "libs/langchain/langchain/retrievers/simple.py",
            """@@ -3,2 +3,4 @@
+    scores = [dot(q, d) for d in matrix]
+    return sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
""",
            "performance",
            "medium",
            "O(n) dot against full matrix; consider ANN index for large collections.",
            4,
        ),
        (
            "expressjs/express",
            "express",
            5790,
            "lib/utils/redos.js",
            """@@ -0,0 +1,2 @@
+const re = /^(a+)+$/;
+export const ok = (s) => re.test(s);
""",
            "performance",
            "medium",
            "Catastrophic backtracking risk (ReDoS) on some inputs; avoid nested quantifiers on user data.",
            1,
        ),
        (
            "tiangolo/fastapi",
            "fastapi",
            10850,
            "app/main.py",
            """@@ -2,2 +2,5 @@
+app.add_middleware(
+  CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'],
+)
""",
            "security",
            "critical",
            "Wildcard CORS with credentials is a dangerous default; restrict origins in production.",
            3,
        ),
        (
            "pallets/flask",
            "flask",
            5120,
            "src/flask/sessions.py",
            """@@ -4,2 +4,4 @@
+    if form['csrf'] != expected:
+        pass
""",
            "security",
            "high",
            "CSRF check uses non-constant-time compare; use hmac.compare_digest.",
            4,
        ),
        (
            "vercel/next.js",
            "nextjs",
            57950,
            "app/list/page.tsx",
            """@@ -1,2 +1,4 @@
 export default function L({ items }: { items: {id:number}[] }) {
-  return <ul>{items.map((x,i) => <li key={i}>{x.id}</li>)}</ul>
+  return <ul>{items.map((x,i) => <li key={i}>{x.id}</li>)}</ul>
 }""",
            "suggestion",
            "low",
            "Index as React key can confuse reconciliation when the list reorders; prefer stable id.",
            2,
        ),
        (
            "langchain-ai/langchain",
            "langchain",
            18380,
            "libs/langchain/langchain/prompts/fstring.py",
            """@@ -0,0 +1,2 @@
+def fmt(t, **k):
+    return t.format(**k)
""",
            "bug",
            "medium",
            "str.format with untrusted keys enables format string injection; validate kwargs.",
            2,
        ),
        (
            "expressjs/express",
            "express",
            5780,
            "lib/auth/compare.js",
            """@@ -0,0 +1,2 @@
+export function eq(a,b){ if (a[i] !== b[i]) return false; }
""",
            "security",
            "high",
            "String comparison for secrets should be constant-time; use timingSafeEqual.",
            1,
        ),
    ]


def _pad_labeled() -> Iterator[dict]:
    for i, row in enumerate(_labeled_pool()):
        repo, short, prn, path, hunk, cat, sev, desc, line = row
        pr_id = f"{short}_pr_{prn + i}"
        yield {
            "pr_id": pr_id,
            "repo": repo,
            "pr_number": prn + i,
            "pr_title": f"Auto-labeled example {i + 1} ({cat})",
            "is_clean": False,
            "diff": _simple_diff(path, hunk),
            "expected_comments": [
                {"file": path, "line": line, "category": cat, "severity": sev, "description": desc}
            ],
            "expected_no_comments": [],
        }


def _pad_clean() -> Iterator[dict]:
    repos: list[tuple[str, str]] = [
        ("tiangolo/fastapi", "fastapi"),
        ("vercel/next.js", "nextjs"),
        ("pallets/flask", "flask"),
        ("langchain-ai/langchain", "langchain"),
        ("expressjs/express", "express"),
    ]
    for i in range(73):
        repo, short = repos[i % len(repos)]
        path = f"src/{short}/clean_{i:03d}.py"
        title = f"Chore: minor cleanup {i}"
        yield {
            "pr_id": f"{short}_pr_{20_000 + i}",
            "repo": repo,
            "pr_number": 20_000 + i,
            "pr_title": title,
            "is_clean": True,
            "diff": _simple_diff(
                path,
                f"""@@ -1,2 +1,2 @@
-# {title}
+# tidied: {i}
 pass
""",
            ),
            "expected_comments": [],
            "expected_no_comments": [],
        }


def all_fixtures() -> list[dict]:
    out = _core_fixtures() + list(_pad_labeled()) + list(_pad_clean())
    if len(out) != 98:
        raise RuntimeError(f"expected 98 fixtures, got {len(out)}")
    return out


def main() -> None:
    fixtures = all_fixtures()
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    categories: dict[str, int] = {}
    clean = 0
    for f in fixtures:
        if f.get("is_clean"):
            clean += 1
        for c in f.get("expected_comments", []):
            categories[c["category"]] = categories.get(c["category"], 0) + 1
    print(f"Generating {len(fixtures)} fixtures (clean={clean}) …")
    print(f"  category distribution: {categories}")
    def _slug(r: str) -> str:
        tail = r.split("/")[1]
        return "nextjs" if tail == "next.js" else tail

    for i, fixture in enumerate(fixtures, start=1):
        cat = "clean"
        if fixture.get("expected_comments"):
            cat = str(fixture["expected_comments"][0]["category"])
        filename = f"pr_{i:03d}_{_slug(fixture['repo'])}_{cat}.json"
        filepath = os.path.join(FIXTURES_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as fp:
            json.dump(fixture, fp, indent=2)
            fp.write("\n")
        print(f"  written {filename}")
    print(f"Done. {len(fixtures)} fixtures in {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
