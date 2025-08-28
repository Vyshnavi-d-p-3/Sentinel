"""Unit tests for the repo walker that feeds the indexing CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.retrieval.repo_walker import walk_repo


def _write(root: Path, rel: str, content: str | bytes) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        target.write_bytes(content)
    else:
        target.write_text(content, encoding="utf-8")


def test_walks_supported_files_and_returns_posix_relpaths(tmp_path: Path) -> None:
    _write(tmp_path, "src/main.py", "print('hi')\n")
    _write(tmp_path, "src/util.ts", "export const x = 1;\n")
    _write(tmp_path, "README.md", "# repo\n")

    files, stats = walk_repo(tmp_path)

    # Posix-style separators in returned keys (stable across platforms).
    assert set(files.keys()) == {"src/main.py", "src/util.ts", "README.md"}
    assert stats.files_yielded == 3
    assert stats.files_skipped_extension == 0
    assert stats.bytes_yielded > 0


def test_excluded_directories_are_pruned(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "x = 1\n")
    _write(tmp_path, ".git/HEAD", "ref: refs/heads/main\n")
    _write(tmp_path, "node_modules/lib/index.js", "module.exports = 1\n")
    _write(tmp_path, "__pycache__/foo.cpython-312.pyc", b"\x00\x01\x02")

    files, _ = walk_repo(tmp_path)

    assert set(files.keys()) == {"app.py"}


def test_unknown_extensions_and_lockfiles_are_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "main.py", "x = 1\n")
    _write(tmp_path, "package-lock.json", '{"lockfileVersion": 2}\n')
    _write(tmp_path, "image.png", b"\x89PNG\r\n\x1a\n")  # binary, no allowlisted ext
    _write(tmp_path, "vendor/lib.min.js", "var x=1;")

    files, stats = walk_repo(tmp_path)

    assert set(files.keys()) == {"main.py"}
    assert stats.files_skipped_generated >= 1  # package-lock.json
    assert stats.files_skipped_extension >= 1  # image.png


def test_max_bytes_skips_oversized_files(tmp_path: Path) -> None:
    _write(tmp_path, "small.py", "x = 1\n")
    _write(tmp_path, "huge.py", "x = 1\n" * 5_000)  # ~30 KB

    files, stats = walk_repo(tmp_path, max_bytes=1024)

    assert "small.py" in files
    assert "huge.py" not in files
    assert stats.files_skipped_size == 1


def test_binary_files_with_allowlisted_extension_are_skipped(tmp_path: Path) -> None:
    """A .py file containing a NUL byte still gets dropped — keeps embeddings clean."""
    _write(tmp_path, "broken.py", b"def ok():\n    pass\n\x00\x01garbage\n")
    _write(tmp_path, "ok.py", "def ok():\n    pass\n")

    files, stats = walk_repo(tmp_path)

    assert set(files.keys()) == {"ok.py"}
    assert stats.files_skipped_binary == 1


def test_empty_files_are_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "blank.py", "")
    _write(tmp_path, "ok.py", "x = 1\n")

    files, _ = walk_repo(tmp_path)

    assert set(files.keys()) == {"ok.py"}


def test_max_files_caps_walk_for_giant_monorepos(tmp_path: Path) -> None:
    for i in range(20):
        _write(tmp_path, f"pkg/file_{i}.py", f"x = {i}\n")

    files, _ = walk_repo(tmp_path, max_files=5)

    assert len(files) == 5


def test_missing_root_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        walk_repo(tmp_path / "does-not-exist")
