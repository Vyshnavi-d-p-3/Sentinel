"""
Walk a local checkout and yield ``(file_path, content)`` pairs suitable for
embedding.

Filtering rules (kept aligned with the chunker's language list):

- Skip directories that are noise (``.git``, ``node_modules``, ``__pycache__``,
  build outputs, etc.) — controlled by ``EXCLUDED_DIRS``.
- Only yield files whose suffix is in ``CODE_FILE_EXTENSIONS`` — anything else
  is unlikely to produce useful embeddings.
- Skip lockfiles, minified bundles, and snapshots (``GENERATED_FILE_SUFFIXES``)
  even when their extension would otherwise match.
- Skip files larger than ``max_bytes`` (default 256 KiB) to avoid blowing the
  embedding budget on vendored libs and giant generated SQL.
- Skip empty files and binary-looking files (NUL byte heuristic).

Paths returned are POSIX-style relative to ``root`` so the same path is stable
across platforms and matches what the diff parser produces.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# Mirrors backend.app.retrieval.chunker._detect_definitions language coverage,
# plus a few common config/markup formats whose verbatim chunks still help BM25.
CODE_FILE_EXTENSIONS: frozenset[str] = frozenset({
    ".py",
    ".js", ".jsx", ".ts", ".tsx",
    ".go",
    ".java", ".kt",
    ".rb",
    ".rs",
    ".c", ".h", ".cpp", ".hpp", ".cc",
    ".cs",
    ".php",
    ".swift",
    ".scala",
    ".sh", ".bash",
    ".sql",
    ".yml", ".yaml",
    ".toml",
    ".md",
})

EXCLUDED_DIRS: frozenset[str] = frozenset({
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".env",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    ".cache",
    "coverage",
    ".idea",
    ".vscode",
    "vendor",
    ".terraform",
})

GENERATED_FILE_SUFFIXES: tuple[str, ...] = (
    ".min.js",
    ".min.css",
    ".bundle.js",
    ".lock",
    "-lock.json",
    "package-lock.json",
    "yarn.lock",
    "Cargo.lock",
    "Gemfile.lock",
    "poetry.lock",
    "composer.lock",
    ".snap",
    ".pb.go",
    ".pb.py",
    "_pb2.py",
)

DEFAULT_MAX_BYTES = 256 * 1024  # 256 KiB per file
DEFAULT_MAX_FILES = 5_000  # safety cap for monorepos


@dataclass(frozen=True)
class WalkStats:
    """Per-walk telemetry — handy for the CLI's summary line."""

    files_yielded: int
    files_skipped_extension: int
    files_skipped_size: int
    files_skipped_binary: int
    files_skipped_generated: int
    bytes_yielded: int


def _looks_generated(path: Path) -> bool:
    name = path.name
    return any(name.endswith(suffix) for suffix in GENERATED_FILE_SUFFIXES)


def _looks_binary(sample: bytes) -> bool:
    """NUL byte in the first 4 KiB strongly suggests binary content."""
    return b"\x00" in sample


def walk_repo(
    root: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_files: int = DEFAULT_MAX_FILES,
) -> tuple[dict[str, str], WalkStats]:
    """
    Walk ``root`` and return ``({relpath: content}, stats)``.

    Stops yielding once ``max_files`` is reached so a misconfigured monorepo
    can't accidentally trigger a multi-million-token embedding bill.
    """
    root_path = Path(root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(f"Repo root does not exist or is not a directory: {root}")

    files: dict[str, str] = {}
    skipped_ext = 0
    skipped_size = 0
    skipped_binary = 0
    skipped_generated = 0
    bytes_yielded = 0

    for entry in _iter_files(root_path):
        if len(files) >= max_files:
            logger.warning("Reached max_files=%s; halting walk early", max_files)
            break

        if _looks_generated(entry):
            skipped_generated += 1
            continue

        if entry.suffix.lower() not in CODE_FILE_EXTENSIONS:
            skipped_ext += 1
            continue

        try:
            size = entry.stat().st_size
        except OSError:
            skipped_size += 1
            continue
        if size == 0 or size > max_bytes:
            skipped_size += 1
            continue

        try:
            with entry.open("rb") as fh:
                head = fh.read(4096)
                if _looks_binary(head):
                    skipped_binary += 1
                    continue
                body = head + fh.read()
        except OSError:
            skipped_binary += 1
            continue

        try:
            content = body.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content = body.decode("latin-1")
            except UnicodeDecodeError:
                skipped_binary += 1
                continue

        # Defense-in-depth: refuse paths that resolve outside ``root_path``.
        # ``_iter_files`` already skips symlinks, but a tricky bind mount or
        # NTFS junction could still escape — fail closed if it does.
        try:
            resolved = entry.resolve()
            rel = resolved.relative_to(root_path).as_posix()
        except (ValueError, OSError):
            logger.warning("Skipping path outside repo root: %s", entry)
            continue
        files[rel] = content
        bytes_yielded += size

    return files, WalkStats(
        files_yielded=len(files),
        files_skipped_extension=skipped_ext,
        files_skipped_size=skipped_size,
        files_skipped_binary=skipped_binary,
        files_skipped_generated=skipped_generated,
        bytes_yielded=bytes_yielded,
    )


def _iter_files(root: Path) -> Iterator[Path]:
    """Depth-first walk that prunes excluded directories in-place."""
    stack: list[Path] = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                # Symlinks can loop or escape the repo root; safest to skip.
                continue
            if entry.is_dir():
                if entry.name in EXCLUDED_DIRS:
                    continue
                stack.append(entry)
            elif entry.is_file():
                yield entry
