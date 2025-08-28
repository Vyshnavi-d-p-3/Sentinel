"""
Operator CLI for the retrieval index.

Usage examples:

    # Index a local checkout (no GitHub round-trip required):
    python -m app.retrieval.cli index-repo \\
        --path /path/to/checkout \\
        --full-name owner/repo \\
        --github-id 123456789

    # Inspect what's currently indexed for a repo:
    python -m app.retrieval.cli show-repo --full-name owner/repo

The ``index-repo`` command:
1. Walks the local checkout (size cap, language allowlist, generated-file filter).
2. Upserts a ``Repo`` row keyed on ``--github-id`` (use any negative integer
   for a sandbox repo with no GitHub origin).
3. Streams the file map through ``EmbeddingPipeline.embed_repo``, which
   chunks → embeds (Voyage if ``VOYAGEAI_API_KEY`` is set, deterministic
   mock otherwise) → upserts into ``repo_embeddings``.

The CLI is intentionally synchronous-looking — it runs the async pipeline
under ``asyncio.run`` so it works the same from a shell or a Makefile target.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from app.core.database import async_session
from app.models.database import Repo, RepoEmbedding
from app.retrieval.indexer import EmbeddingPipeline
from app.retrieval.repo_walker import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_FILES,
    WalkStats,
    walk_repo,
)
from app.services.review_store import get_or_create_repo

logger = logging.getLogger("sentinel.cli.retrieval")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.retrieval.cli",
        description="Sentinel retrieval index CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    index_p = sub.add_parser(
        "index-repo",
        help="Walk a local checkout and (re)build its embeddings.",
    )
    index_p.add_argument("--path", required=True, help="Path to the local repo checkout")
    index_p.add_argument("--full-name", required=True, help="owner/repo (used to dedupe Repo row)")
    index_p.add_argument(
        "--github-id",
        type=int,
        default=None,
        help="GitHub numeric repo id; if omitted a stable negative hash of full-name is used",
    )
    index_p.add_argument(
        "--installation-id",
        type=int,
        default=0,
        help="GitHub App installation id (defaults to 0 for local-only sandboxes)",
    )
    index_p.add_argument(
        "--commit-ts",
        default=None,
        help="ISO-8601 timestamp recorded as last_commit_at for recency boost (default=now)",
    )
    index_p.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help=f"Skip files larger than this many bytes (default {DEFAULT_MAX_BYTES})",
    )
    index_p.add_argument(
        "--max-files",
        type=int,
        default=DEFAULT_MAX_FILES,
        help=f"Stop walking after N files (default {DEFAULT_MAX_FILES})",
    )
    index_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Walk and report stats, but do not call the embedder or DB",
    )
    index_p.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose logging",
    )

    show_p = sub.add_parser(
        "show-repo",
        help="Print stats about an indexed repo (chunk count, file count, last update).",
    )
    show_p.add_argument("--full-name", required=True)

    return parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stable_github_id(full_name: str) -> int:
    """Negative deterministic id for sandboxes that have no real GitHub repo."""
    import hashlib

    digest = hashlib.sha256(full_name.encode("utf-8")).digest()
    n = int.from_bytes(digest[:8], "big", signed=False)
    return -(n % (2**62))  # negative + within bigint range


def _parse_commit_ts(raw: str | None) -> datetime:
    if not raw:
        return datetime.utcnow()
    try:
        # Accept both naive and timezone-aware ISO strings.
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SystemExit(f"--commit-ts is not valid ISO-8601: {raw!r}") from exc
    if ts.tzinfo is not None:
        ts = ts.astimezone(UTC).replace(tzinfo=None)
    return ts


def _format_stats(stats: WalkStats) -> str:
    return (
        f"yielded={stats.files_yielded} "
        f"skipped_ext={stats.files_skipped_extension} "
        f"skipped_size={stats.files_skipped_size} "
        f"skipped_binary={stats.files_skipped_binary} "
        f"skipped_generated={stats.files_skipped_generated} "
        f"bytes={stats.bytes_yielded:,}"
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def _cmd_index_repo(args: argparse.Namespace) -> int:
    root = Path(args.path).expanduser()
    print(f"[walk] root={root}")
    files, stats = walk_repo(root, max_bytes=args.max_bytes, max_files=args.max_files)
    print(f"[walk] {_format_stats(stats)}")

    if not files:
        print("[index] no eligible files; nothing to do")
        return 0

    if args.dry_run:
        print("[index] --dry-run set; skipping embedder + DB writes")
        return 0

    commit_ts = _parse_commit_ts(args.commit_ts)
    github_id = args.github_id if args.github_id is not None else _stable_github_id(args.full_name)

    pipeline = EmbeddingPipeline()

    async with async_session() as session:
        try:
            repo = await get_or_create_repo(
                session,
                github_id=github_id,
                full_name=args.full_name,
                installation_id=args.installation_id,
            )
            await session.flush()

            chunks_written = await pipeline.embed_repo(
                session,
                repo_id=repo.id,
                files=files,
                last_commit_at=commit_ts,
                replace_existing=True,
            )
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.exception("Indexing failed for %s", args.full_name)
            print(f"[index] FAILED: {exc}", file=sys.stderr)
            return 2

    print(
        f"[index] OK  repo={args.full_name} repo_id={repo.id} "
        f"files={stats.files_yielded} chunks={chunks_written} "
        f"last_commit_at={commit_ts.isoformat()}"
    )
    return 0


async def _cmd_show_repo(args: argparse.Namespace) -> int:
    async with async_session() as session:
        repo_q = await session.execute(select(Repo).where(Repo.full_name == args.full_name))
        repo = repo_q.scalar_one_or_none()
        if repo is None:
            print(f"[show] no Repo row for full_name={args.full_name!r}", file=sys.stderr)
            return 1

        chunk_count_q = await session.execute(
            select(func.count(RepoEmbedding.id)).where(RepoEmbedding.repo_id == repo.id)
        )
        file_count_q = await session.execute(
            select(func.count(func.distinct(RepoEmbedding.file_path))).where(
                RepoEmbedding.repo_id == repo.id
            )
        )
        latest_q = await session.execute(
            select(func.max(RepoEmbedding.updated_at)).where(RepoEmbedding.repo_id == repo.id)
        )

        chunks = int(chunk_count_q.scalar_one() or 0)
        files = int(file_count_q.scalar_one() or 0)
        last_updated = latest_q.scalar_one()

        print(f"repo:        {repo.full_name}")
        print(f"repo_id:     {repo.id}")
        print(f"github_id:   {repo.github_id}")
        print(f"chunks:      {chunks}")
        print(f"files:       {files}")
        print(f"updated_at:  {last_updated.isoformat() if last_updated else 'never'}")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )

    if args.command == "index-repo":
        return asyncio.run(_cmd_index_repo(args))
    if args.command == "show-repo":
        return asyncio.run(_cmd_show_repo(args))
    return 1  # unreachable: argparse enforces a subcommand


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
