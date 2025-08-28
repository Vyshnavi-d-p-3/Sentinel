"""GitHub App API client for PR comments and check runs."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.models.review_output import ReviewComment

logger = logging.getLogger(__name__)

_SEVERITY_EMOJI = {
    "critical": "🚨",
    "high": "🔴",
    "medium": "🟠",
    "low": "🟡",
}


@dataclass(frozen=True)
class GithubPublishResult:
    """IDs of artifacts posted to GitHub."""

    comment_ids: list[int]
    check_run_id: int | None


def _format_comment_body(comment: ReviewComment) -> str:
    emoji = _SEVERITY_EMOJI.get(comment.severity.value, "💬")
    header = f"{emoji} **[{comment.category.value}] {comment.title}**"
    pieces = [header, "", comment.body]
    if comment.suggestion:
        pieces.extend(["", "```suggestion", comment.suggestion, "```"])
    confidence_pct = int(round(comment.confidence * 100))
    pieces.extend(["", f"_Confidence: {confidence_pct}% • Sentinel AI Review_"])
    return "\n".join(pieces)


class GithubClient:
    """Minimal client for publishing review artifacts."""

    def __init__(self, token: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def post_inline_comments(
        self,
        *,
        repo_full_name: str,
        pr_number: int,
        head_sha: str,
        comments: list[ReviewComment],
    ) -> list[int]:
        """Post per-line review comments and return GitHub comment IDs."""
        posted_ids: list[int] = []
        if not comments:
            return posted_ids

        async with httpx.AsyncClient(timeout=30.0) as client:
            for comment in comments:
                payload = {
                    "body": _format_comment_body(comment),
                    "commit_id": head_sha,
                    "path": comment.file_path,
                    "line": comment.line_number,
                    "side": "RIGHT",
                }
                try:
                    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/comments"
                    resp = await client.post(url, headers=self._headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    comment_id = data.get("id")
                    if isinstance(comment_id, int):
                        posted_ids.append(comment_id)
                except Exception as exc:
                    # Keep best-effort behavior: one bad anchor should not abort all posts.
                    logger.warning(
                        "Failed posting inline comment path=%s line=%s: %s",
                        comment.file_path,
                        comment.line_number,
                        exc,
                    )
        return posted_ids

    async def create_check_run(
        self,
        *,
        repo_full_name: str,
        head_sha: str,
        summary: str,
        conclusion: str,
        title: str = "Sentinel AI Review",
    ) -> int | None:
        """Create a check run summarizing review outcome."""
        payload = {
            "name": "Sentinel Review",
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": {
                "title": title,
                "summary": summary[:65535] if summary else "Sentinel completed review.",
            },
        }
        url = f"https://api.github.com/repos/{repo_full_name}/check-runs"
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(url, headers=self._headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                check_id = data.get("id")
                return check_id if isinstance(check_id, int) else None
            except Exception as exc:
                logger.warning("Failed creating check run: %s", exc)
                return None

    async def publish_review(
        self,
        *,
        repo_full_name: str,
        pr_number: int,
        head_sha: str,
        summary: str,
        comments: list[ReviewComment],
        quality_score: float | None,
    ) -> GithubPublishResult:
        comment_ids = await self.post_inline_comments(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            head_sha=head_sha,
            comments=comments,
        )
        # Basic pass/fail policy: fail check on any high-severity issue.
        has_high = any(c.severity.value in {"critical", "high"} for c in comments)
        low_score = quality_score is not None and quality_score < 5.0
        conclusion = "failure" if (has_high or low_score) else "success"
        check_run_id = await self.create_check_run(
            repo_full_name=repo_full_name,
            head_sha=head_sha,
            summary=summary,
            conclusion=conclusion,
        )
        return GithubPublishResult(comment_ids=comment_ids, check_run_id=check_run_id)
