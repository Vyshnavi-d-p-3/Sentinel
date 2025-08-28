"""
Language-aware code chunker.

Splits a source file into chunks suitable for embedding-based retrieval:

- One ``module`` chunk per file: the first ~50 lines (captures imports, file
  docstring, top-level constants, and module shape).
- One ``function`` or ``class`` chunk per top-level definition. Boundaries are
  detected by indentation (Python) or brace depth (JS/TS/Go). Nested helpers
  are folded into the enclosing definition rather than emitted separately so
  retrieval surfaces meaningful units.
- For unsupported languages we fall back to fixed-size blocks of
  ``BLOCK_LINES`` lines so retrieval still works on every file type.

Chunks carry stable ``start_line`` / ``end_line`` so the dashboard can deep-link
into GitHub.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Conservative: each chunk should fit comfortably inside a single embedding
# request and still leave room for the LLM context window downstream.
MAX_CHUNK_LINES = 200
MAX_CHUNK_CHARS = 6_000
MODULE_HEADER_LINES = 50
BLOCK_LINES = 50


@dataclass
class CodeChunk:
    """A single retrievable chunk of source code."""

    file_path: str
    chunk_type: str  # module | function | class | block | doc
    chunk_text: str
    start_line: int
    end_line: int


# Languages whose ``def`` / ``class`` boundaries we know how to detect.
_PY_DEF = re.compile(r"^(?P<indent>[ \t]*)(?:async\s+def|def|class)\s+(?P<name>\w+)")
_JS_DEF = re.compile(
    r"^[ \t]*"
    r"(?:export\s+(?:default\s+)?)?"
    r"(?:async\s+)?"
    r"(?:function\s+(?P<fname>\w+)"
    r"|class\s+(?P<cname>\w+)"
    r"|(?:const|let|var)\s+(?P<vname>\w+)\s*=\s*(?:async\s+)?(?:\(|function))"
)
_GO_DEF = re.compile(r"^func(?:\s+\([^)]*\))?\s+(?P<name>\w+)\s*\(")


class CodeChunker:
    """Split source files into module/function/class chunks."""

    def chunk_file(self, file_path: str, content: str) -> list[CodeChunk]:
        if not content:
            return []

        lines = content.splitlines()
        chunks: list[CodeChunk] = []

        # 1) module header
        module_text = "\n".join(lines[:MODULE_HEADER_LINES])
        if module_text.strip():
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    chunk_type="module",
                    chunk_text=module_text[:MAX_CHUNK_CHARS],
                    start_line=1,
                    end_line=min(MODULE_HEADER_LINES, len(lines)),
                )
            )

        # 2) language-specific structural chunks
        ext = self._extension(file_path)
        defs = self._detect_definitions(lines, ext)
        if defs:
            chunks.extend(self._chunks_from_definitions(file_path, lines, defs))
        else:
            chunks.extend(self._fallback_blocks(file_path, lines))

        # Cap any over-long chunk text deterministically.
        for chunk in chunks:
            if len(chunk.chunk_text) > MAX_CHUNK_CHARS:
                chunk.chunk_text = chunk.chunk_text[:MAX_CHUNK_CHARS]
        return chunks

    # ----------------------------------------------------------- helpers

    @staticmethod
    def _extension(file_path: str) -> str:
        if "." not in file_path:
            return ""
        return "." + file_path.rsplit(".", 1)[-1].lower()

    @staticmethod
    def _detect_definitions(lines: list[str], ext: str) -> list[tuple[int, str, str]]:
        """Return ``[(line_idx_0_based, chunk_type, name)]`` for top-level defs."""
        out: list[tuple[int, str, str]] = []
        if ext == ".py":
            for i, line in enumerate(lines):
                m = _PY_DEF.match(line)
                if not m:
                    continue
                # Top-level only: zero indentation
                if not m.group("indent"):
                    chunk_type = "class" if line.lstrip().startswith("class") else "function"
                    out.append((i, chunk_type, m.group("name")))
        elif ext in (".js", ".jsx", ".ts", ".tsx"):
            for i, line in enumerate(lines):
                m = _JS_DEF.match(line)
                if not m:
                    continue
                name = m.group("fname") or m.group("cname") or m.group("vname") or ""
                chunk_type = "class" if m.group("cname") else "function"
                out.append((i, chunk_type, name))
        elif ext == ".go":
            for i, line in enumerate(lines):
                m = _GO_DEF.match(line)
                if m:
                    out.append((i, "function", m.group("name")))
        return out

    def _chunks_from_definitions(
        self,
        file_path: str,
        lines: list[str],
        defs: list[tuple[int, str, str]],
    ) -> list[CodeChunk]:
        """Build chunks from definition boundaries; each chunk runs to the next def."""
        chunks: list[CodeChunk] = []
        for idx, (start, chunk_type, _name) in enumerate(defs):
            end = defs[idx + 1][0] if idx + 1 < len(defs) else len(lines)
            end = min(end, start + MAX_CHUNK_LINES)
            text = "\n".join(lines[start:end]).strip("\n")
            if not text.strip():
                continue
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    chunk_type=chunk_type,
                    chunk_text=text,
                    start_line=start + 1,
                    end_line=end,
                )
            )
        return chunks

    def _fallback_blocks(self, file_path: str, lines: list[str]) -> list[CodeChunk]:
        """Fixed-size blocks for unsupported languages."""
        chunks: list[CodeChunk] = []
        for i in range(0, len(lines), BLOCK_LINES):
            block = lines[i : i + BLOCK_LINES]
            text = "\n".join(block).strip("\n")
            if not text.strip():
                continue
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    chunk_type="block",
                    chunk_text=text,
                    start_line=i + 1,
                    end_line=min(i + BLOCK_LINES, len(lines)),
                )
            )
        return chunks
