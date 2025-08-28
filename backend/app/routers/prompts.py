"""Prompt version management — history, diff view, activate."""

from __future__ import annotations

import difflib
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.core.database import async_session
from app.models.database import Prompt
from app.prompts.review_prompts import (
    CROSSREF_SYSTEM_PROMPT,
    REVIEW_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
    TRIAGE_SYSTEM_PROMPT,
    review_prompt_template_hash,
)

router = APIRouter()


_IN_MEMORY_NAME = "sentinel_review_pipeline"
_IN_MEMORY_SOURCE = "app/prompts/review_prompts.py"


class PromptSummary(BaseModel):
    hash: str
    name: str
    version: int
    description: str | None = None
    is_active: bool
    created_at: datetime | None = None
    source: str = Field(
        description="Where this prompt came from — 'db' for persisted rows, 'code' for the "
        "in-memory template set bundled with the deploy."
    )


class PromptDetail(PromptSummary):
    system_prompt: str
    user_template: str


class PromptListResponse(BaseModel):
    active: PromptSummary | None
    prompts: list[PromptSummary]


class PromptDiffEntry(BaseModel):
    a: str
    b: str
    field: str
    unified_diff: str
    added_lines: int
    removed_lines: int


class PromptDiffResponse(BaseModel):
    a: PromptSummary
    b: PromptSummary
    diffs: list[PromptDiffEntry]


def _in_memory_prompt() -> PromptDetail:
    """Construct the 'code' prompt card from the bundled review_prompts module."""
    system_prompt = "\n\n---\n\n".join(
        [
            f"# Step 1 — Triage\n{TRIAGE_SYSTEM_PROMPT.strip()}",
            f"# Step 2 — Deep Review\n{REVIEW_SYSTEM_PROMPT.strip()}",
            f"# Step 3 — Cross-Reference\n{CROSSREF_SYSTEM_PROMPT.strip()}",
            f"# Step 4 — Synthesis\n{SYNTHESIS_SYSTEM_PROMPT.strip()}",
        ]
    )
    return PromptDetail(
        hash=review_prompt_template_hash(),
        name=_IN_MEMORY_NAME,
        version=1,
        description=(
            "Active prompt bundle used by the review orchestrator. Sourced from "
            f"{_IN_MEMORY_SOURCE} and hashed per deploy for reproducibility."
        ),
        is_active=True,
        created_at=None,
        source="code",
        system_prompt=system_prompt,
        user_template="(user templates are assembled per-step — see review_prompts.py)",
    )


def _row_to_summary(row: Prompt) -> PromptSummary:
    return PromptSummary(
        hash=row.hash,
        name=row.name,
        version=int(row.version),
        description=row.description,
        is_active=bool(row.is_active),
        created_at=row.created_at,
        source="db",
    )


def _row_to_detail(row: Prompt) -> PromptDetail:
    return PromptDetail(
        hash=row.hash,
        name=row.name,
        version=int(row.version),
        description=row.description,
        is_active=bool(row.is_active),
        created_at=row.created_at,
        source="db",
        system_prompt=row.system_prompt,
        user_template=row.user_template,
    )


@router.get("/", response_model=PromptListResponse)
async def list_prompts():
    """
    Return the currently-active prompt plus the full history.

    The active card is always included — even when the Prompt table is empty — by
    falling back to the in-memory template hash so the dashboard never looks broken
    on a fresh deploy.
    """
    active_card: PromptSummary | None = None
    prompts: list[PromptSummary] = []

    async with async_session() as session:
        rows = (
            await session.execute(select(Prompt).order_by(Prompt.created_at.desc().nullslast()))
        ).scalars().all()

    db_active = next((r for r in rows if bool(r.is_active)), None)
    if db_active is not None:
        active_card = _row_to_summary(db_active)

    prompts.extend(_row_to_summary(r) for r in rows)

    # Always surface the in-memory bundle so the hash pinning story is visible.
    in_memory = _in_memory_prompt()
    code_card = PromptSummary(**in_memory.model_dump(exclude={"system_prompt", "user_template"}))
    # Don't double-list: if the code hash already exists in DB, keep the DB row.
    if not any(p.hash == code_card.hash for p in prompts):
        prompts.insert(0, code_card)

    if active_card is None:
        active_card = code_card

    return PromptListResponse(active=active_card, prompts=prompts)


@router.get("/{prompt_hash}", response_model=PromptDetail)
async def get_prompt(prompt_hash: str):
    """Return the full system + user template for a given prompt hash."""
    in_memory = _in_memory_prompt()
    if prompt_hash == in_memory.hash:
        return in_memory

    async with async_session() as session:
        row = (
            await session.execute(select(Prompt).where(Prompt.hash == prompt_hash))
        ).scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Prompt {prompt_hash} not found")
    return _row_to_detail(row)


@router.get("/{prompt_hash}/diff", response_model=PromptDiffResponse)
async def diff_prompt(
    prompt_hash: str,
    against: str = Query(..., description="The hash to diff against."),
):
    """Return a unified diff between two prompt versions (``prompt_hash`` vs ``against``)."""
    a = await get_prompt(prompt_hash)
    b = await get_prompt(against)

    diffs: list[PromptDiffEntry] = []
    for field in ("system_prompt", "user_template"):
        a_text: str = getattr(a, field) or ""
        b_text: str = getattr(b, field) or ""
        if a_text == b_text:
            continue
        udiff = _unified_diff(a_text, b_text, fromfile=f"{a.hash[:7]}/{field}", tofile=f"{b.hash[:7]}/{field}")
        added = sum(1 for line in udiff.splitlines() if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in udiff.splitlines() if line.startswith("-") and not line.startswith("---"))
        diffs.append(
            PromptDiffEntry(
                a=a.hash,
                b=b.hash,
                field=field,
                unified_diff=udiff,
                added_lines=added,
                removed_lines=removed,
            )
        )

    return PromptDiffResponse(
        a=PromptSummary(**a.model_dump(exclude={"system_prompt", "user_template"})),
        b=PromptSummary(**b.model_dump(exclude={"system_prompt", "user_template"})),
        diffs=diffs,
    )


@router.post("/activate/{prompt_hash}", response_model=PromptSummary)
async def activate_prompt(prompt_hash: str):
    """Deactivate the current active prompt and activate the specified one."""
    async with async_session() as session:
        target = (
            await session.execute(select(Prompt).where(Prompt.hash == prompt_hash))
        ).scalar_one_or_none()
        if target is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Prompt {prompt_hash} not persisted. Only DB-stored prompts can be "
                    "activated; the in-memory bundle is always active by default."
                ),
            )
        await session.execute(update(Prompt).where(Prompt.is_active.is_(True)).values(is_active=False))
        target.is_active = True
        await session.commit()
        await session.refresh(target)
        return _row_to_summary(target)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unified_diff(a: str, b: str, *, fromfile: str, tofile: str) -> str:
    return "".join(
        difflib.unified_diff(
            a.splitlines(keepends=True),
            b.splitlines(keepends=True),
            fromfile=fromfile,
            tofile=tofile,
            n=3,
        )
    )


def _now_iso(dt: datetime | None) -> Any:
    return dt.isoformat() if dt else None
