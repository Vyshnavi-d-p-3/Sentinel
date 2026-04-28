"""
Parse unified diffs into structured data for retrieval and LLM context.

Extracts changed files, function signatures, surrounding context (±10 lines),
and import statements. Handles edge cases: binary files, renames, deletions,
files with no newline at EOF.
"""

import re
from dataclasses import dataclass, field


@dataclass
class ChangedFunction:
    name: str
    file_path: str
    start_line: int
    end_line: int
    content: str


@dataclass
class FileChange:
    path: str
    status: str  # added, modified, deleted, renamed, binary
    old_path: str | None = None
    additions: int = 0
    deletions: int = 0
    hunks: list[str] = field(default_factory=list)
    changed_functions: list[ChangedFunction] = field(default_factory=list)
    changed_lines: list[int] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


@dataclass
class ParsedDiff:
    files: list[FileChange]
    total_additions: int = 0
    total_deletions: int = 0

    @property
    def changed_file_paths(self) -> list[str]:
        return [f.path for f in self.files]

    @property
    def has_code_changes(self) -> bool:
        code_extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rs", ".rb"}
        return any(
            any(f.path.endswith(ext) for ext in code_extensions)
            for f in self.files
        )


class DiffParser:
    """
    Parse unified diff format into structured FileChange objects.

    Usage:
        parser = DiffParser()
        result = parser.parse(raw_diff_string)
        for file in result.files:
            print(f"{file.path}: +{file.additions} -{file.deletions}")
    """

    CONTEXT_LINES = 10
    # TODO(vyshnavi): Handle git rename detection (--follow). Currently
    # treats renames as delete + create, missing cross-file analysis.
    HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")
    FUNCTION_PATTERNS = {
        ".py": re.compile(r"^\s*(def|class)\s+(\w+)"),
        ".js": re.compile(r"^\s*(function|class)\s+(\w+)|^\s*(const|let|var)\s+(\w+)\s*=\s*(async\s+)?(\(|function)"),
        ".ts": re.compile(r"^\s*(function|class|interface|type)\s+(\w+)"),
        ".go": re.compile(r"^func\s+(?:\(.*?\)\s+)?(\w+)"),
        ".java": re.compile(r"^\s*(public|private|protected)?\s*(static)?\s*\w+\s+(\w+)\s*\("),
    }

    def parse(self, raw_diff: str) -> ParsedDiff:
        """Parse a complete unified diff string."""
        if not raw_diff or not raw_diff.strip():
            return ParsedDiff(files=[])

        files: list[FileChange] = []
        current: FileChange | None = None
        current_line = 0

        for line in raw_diff.splitlines():
            if line.startswith("diff --git"):
                if current:
                    files.append(current)
                current = self._parse_diff_header(line)
                current_line = 0
            elif current is None:
                continue
            elif line.startswith("Binary files"):
                current.status = "binary"
            elif line.startswith("rename from"):
                current.old_path = line[12:]
                current.status = "renamed"
            elif line.startswith("new file"):
                current.status = "added"
            elif line.startswith("deleted file"):
                current.status = "deleted"
            elif (m := self.HUNK_HEADER.match(line)):
                current_line = int(m.group(3))
                current.hunks.append(line)
            elif line.startswith("+") and not line.startswith("+++"):
                current.additions += 1
                current.changed_lines.append(current_line)
                self._detect_import(current, line[1:])
                current_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                current.deletions += 1
            else:
                current_line += 1

        if current:
            files.append(current)

        total_add = sum(f.additions for f in files)
        total_del = sum(f.deletions for f in files)

        return ParsedDiff(files=files, total_additions=total_add, total_deletions=total_del)

    def _parse_diff_header(self, header: str) -> FileChange:
        """Extract file path from 'diff --git a/path b/path'."""
        parts = header.split(" b/", 1)
        path = parts[1] if len(parts) > 1 else "unknown"
        return FileChange(path=path, status="modified")

    def _detect_import(self, fc: FileChange, line: str) -> None:
        """Track import statements in added lines."""
        stripped = line.strip()
        if stripped.startswith(("import ", "from ", "require(", "const ", "#include")):
            fc.imports.append(stripped)

    def extract_context(self, file_content: str, changed_lines: list[int]) -> str:
        """Extract ±CONTEXT_LINES around each changed line."""
        lines = file_content.splitlines()
        included: set[int] = set()
        for ln in changed_lines:
            start = max(0, ln - self.CONTEXT_LINES)
            end = min(len(lines), ln + self.CONTEXT_LINES + 1)
            included.update(range(start, end))
        return "\n".join(lines[i] for i in sorted(included))

    def detect_functions(self, file_path: str, content: str) -> list[ChangedFunction]:
        """Detect function/class definitions in file content."""
        ext = "." + file_path.rsplit(".", 1)[-1] if "." in file_path else ""
        pattern = self.FUNCTION_PATTERNS.get(ext)
        if not pattern:
            return []

        functions = []
        for i, line in enumerate(content.splitlines(), 1):
            m = pattern.match(line)
            if m:
                name = m.group(2) or m.group(1)
                functions.append(ChangedFunction(
                    name=name, file_path=file_path,
                    start_line=i, end_line=i, content=line.strip(),
                ))
        return functions
