"""Initial schema — repos, reviews, prompts, eval_runs, cost_ledger, feedback, embeddings.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-21 00:00:00

This baseline migration encodes the full ORM defined in
``app.models.database`` so production deployments can boot with
``DB_AUTO_CREATE_TABLES=false`` and run pure Alembic migrations. The pgvector
extension is created up-front because indexes and column types depend on it.
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector extension is required before columns of type ``vector`` exist.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "repos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("github_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("default_branch", sa.Text(), server_default="main"),
        sa.Column("auto_review", sa.Boolean(), server_default=sa.true()),
        sa.Column("daily_token_budget", sa.Integer(), server_default="100000"),
        sa.Column("per_pr_token_cap", sa.Integer(), server_default="20000"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "prompts",
        sa.Column("hash", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_template", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("repos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("pr_title", sa.Text()),
        sa.Column("pr_url", sa.Text()),
        sa.Column("diff_hash", sa.Text(), nullable=False),
        sa.Column("prompt_hash", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="completed"),
        sa.Column("summary", sa.Text()),
        sa.Column("pr_quality_score", sa.Float()),
        sa.Column("review_focus_areas", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("triage_result", postgresql.JSONB()),
        sa.Column("pipeline_step_timings", postgresql.JSONB()),
        sa.Column("github_review_id", sa.Text()),
        sa.Column("check_run_id", sa.Text()),
        sa.Column("comments", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("retrieval_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("repo_id", "pr_number", "diff_hash"),
    )

    op.create_table(
        "eval_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("prompt_hash", sa.Text(), sa.ForeignKey("prompts.hash"), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("dataset_version", sa.Text(), nullable=False),
        sa.Column("security_precision", sa.Float()),
        sa.Column("security_recall", sa.Float()),
        sa.Column("security_f1", sa.Float()),
        sa.Column("bug_precision", sa.Float()),
        sa.Column("bug_recall", sa.Float()),
        sa.Column("bug_f1", sa.Float()),
        sa.Column("perf_precision", sa.Float()),
        sa.Column("perf_recall", sa.Float()),
        sa.Column("perf_f1", sa.Float()),
        sa.Column("style_precision", sa.Float()),
        sa.Column("style_recall", sa.Float()),
        sa.Column("style_f1", sa.Float()),
        sa.Column("overall_precision", sa.Float()),
        sa.Column("overall_recall", sa.Float()),
        sa.Column("overall_f1", sa.Float()),
        sa.Column("total_prs_evaluated", sa.Integer(), nullable=False),
        sa.Column("avg_latency_ms", sa.Float()),
        sa.Column("total_cost_usd", sa.Float()),
        sa.Column("git_commit_sha", sa.Text()),
        sa.Column("ci_run_url", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("run_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "cost_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repos.id"), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reviews.id")),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("pipeline_step", sa.Text(), nullable=False, server_default="review"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "review_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("review_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("repos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("comment_index", sa.Integer()),
        sa.Column("github_comment_id", sa.Text()),
        sa.Column("github_review_id", sa.Text()),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("category", sa.Text()),
        sa.Column("severity", sa.Text()),
        sa.Column("github_user", sa.Text()),
        sa.Column("reply_body", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "review_id", "github_comment_id", "action",
            name="uq_review_feedback_event",
        ),
    )
    op.create_index("ix_review_feedback_review", "review_feedback", ["review_id"])
    op.create_index("ix_review_feedback_repo_created", "review_feedback", ["repo_id", "created_at"])
    op.create_index("ix_review_feedback_action", "review_feedback", ["action"])

    op.create_table(
        "repo_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("repos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("chunk_type", sa.Text(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer()),
        sa.Column("end_line", sa.Integer()),
        sa.Column("embedding", Vector(1024)),
        sa.Column(
            "ts_content",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', chunk_text)", persisted=True),
        ),
        sa.Column("last_commit_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "repo_id", "file_path", "chunk_type", "start_line",
            name="uq_repo_chunk_location",
        ),
    )
    # Vector + BM25 indexes — explicit operator class for ivfflat cosine.
    op.execute(
        "CREATE INDEX ix_repo_embeddings_embedding_ivfflat "
        "ON repo_embeddings USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )
    op.create_index(
        "ix_repo_embeddings_ts_content_gin",
        "repo_embeddings",
        ["ts_content"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_repo_embeddings_repo_recency",
        "repo_embeddings",
        ["repo_id", "last_commit_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_repo_embeddings_repo_recency", table_name="repo_embeddings")
    op.drop_index("ix_repo_embeddings_ts_content_gin", table_name="repo_embeddings")
    op.execute("DROP INDEX IF EXISTS ix_repo_embeddings_embedding_ivfflat")
    op.drop_table("repo_embeddings")
    op.drop_index("ix_review_feedback_action", table_name="review_feedback")
    op.drop_index("ix_review_feedback_repo_created", table_name="review_feedback")
    op.drop_index("ix_review_feedback_review", table_name="review_feedback")
    op.drop_table("review_feedback")
    op.drop_table("cost_ledger")
    op.drop_table("eval_runs")
    op.drop_table("reviews")
    op.drop_table("prompts")
    op.drop_table("repos")
