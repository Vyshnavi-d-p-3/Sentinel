"""Tests for DiffParser — edge cases: binary files, renames, empty diffs."""

import pytest

from app.services.diff_parser import DiffParser


@pytest.fixture
def parser():
    return DiffParser()


class TestDiffParser:
    def test_empty_diff(self, parser):
        result = parser.parse("")
        assert result.files == []
        assert result.total_additions == 0

    def test_simple_modification(self, parser):
        diff = """diff --git a/src/auth.py b/src/auth.py
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,3 +10,4 @@
 existing line
+new line added
-old line removed
"""
        result = parser.parse(diff)
        assert len(result.files) == 1
        assert result.files[0].path == "src/auth.py"
        assert result.files[0].additions == 1
        assert result.files[0].deletions == 1

    def test_new_file(self, parser):
        diff = """diff --git a/src/new.py b/src/new.py
new file mode 100644
--- /dev/null
+++ b/src/new.py
@@ -0,0 +1,3 @@
+import os
+
+print("hello")
"""
        result = parser.parse(diff)
        assert result.files[0].status == "added"
        assert result.files[0].additions == 3

    def test_binary_file(self, parser):
        diff = """diff --git a/image.png b/image.png
Binary files a/image.png and b/image.png differ
"""
        result = parser.parse(diff)
        assert result.files[0].status == "binary"

    def test_multiple_files(self, parser):
        diff = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,1 +1,2 @@
 line
+added
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -1,2 +1,1 @@
 line
-removed
"""
        result = parser.parse(diff)
        assert len(result.files) == 2
        assert result.total_additions == 1
        assert result.total_deletions == 1
