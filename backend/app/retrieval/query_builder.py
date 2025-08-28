"""
Build retrieval queries from a parsed diff file.

The query is intentionally short (<= ~300 chars) so BM25 stays focused and
the dense embedding stays in the model's recommended input range. We use
the file path stem, any function/class names mentioned in the diff hunks,
and key identifiers from added lines.
"""

from __future__ import annotations

import re
from collections import Counter

from app.services.diff_parser import FileChange

# Common words we don't want diluting the BM25 query.
_STOPWORDS = {
    "self", "cls", "this", "args", "kwargs", "return", "true", "false",
    "none", "null", "undefined", "let", "const", "var", "function",
    "class", "def", "async", "await", "if", "else", "elif", "for",
    "while", "try", "except", "throw", "throws", "catch", "import",
    "from", "as", "new", "in", "of", "is", "not", "and", "or",
}

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")
_HUNK_FN = re.compile(r"@@.*?@@\s*(?:def|function|class|func)?\s*([A-Za-z_][A-Za-z0-9_]*)")


def build_query_for_file(file: FileChange, max_terms: int = 12) -> str:
    """Form a concise retrieval query for one changed file."""
    terms: list[str] = []
    stem = file.path.rsplit("/", 1)[-1].split(".", 1)[0]
    if stem:
        terms.append(stem)

    counter: Counter[str] = Counter()
    for hunk in file.hunks:
        for m in _HUNK_FN.finditer(hunk):
            ident = m.group(1)
            if _is_useful_ident(ident):
                counter[ident] += 3  # function-name signal is high

    for fn in file.changed_functions:
        if _is_useful_ident(fn.name):
            counter[fn.name] += 2

    for line in _added_lines_from_hunks(file.hunks):
        for m in _IDENT.finditer(line):
            ident = m.group(0)
            if _is_useful_ident(ident):
                counter[ident] += 1

    for ident, _count in counter.most_common(max_terms):
        if ident not in terms:
            terms.append(ident)
        if len(terms) >= max_terms + 1:
            break

    return " ".join(terms).strip()


def _is_useful_ident(token: str) -> bool:
    if len(token) < 3:
        return False
    if token.isdigit():
        return False
    return token.lower() not in _STOPWORDS


def _added_lines_from_hunks(hunks: list[str]) -> list[str]:
    """Best-effort extraction of added lines from hunk headers (hunk strings here are headers only)."""
    # Our DiffParser stores hunk *headers* in ``hunks``; added-line text is not
    # captured per-file. We only iterate identifiers from the headers themselves
    # (which include the function context after the second ``@@``).
    return hunks
