"""SQLAlchemy ORM models — repos, reviews, prompts, eval_runs, cost_ledger, embeddings."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Repo(Base):
    __tablename__ = "repos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    github_id = Column(BigInteger, unique=True, nullable=False)
    full_name = Column(Text, nullable=False)
    installation_id = Column(BigInteger, nullable=False)
    default_branch = Column(Text, default="main")
    auto_review = Column(Boolean, default=True)
    daily_token_budget = Column(Integer, default=100_000)
    per_pr_token_cap = Column(Integer, default=20_000)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    reviews = relationship("Review", back_populates="repo", cascade="all, delete-orphan")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    pr_number = Column(Integer, nullable=False)
    pr_title = Column(Text)
    pr_url = Column(Text)
    diff_hash = Column(Text, nullable=False)
    prompt_hash = Column(Text, nullable=False)
    model_version = Column(Text, nullable=False)
    status = Column(Text, default="completed")
    summary = Column(Text)
    pr_quality_score = Column(Float)
    review_focus_areas = Column(JSONB, nullable=False, default=list)
    triage_result = Column(JSONB)
    pipeline_step_timings = Column(JSONB)
    github_review_id = Column(Text)
    check_run_id = Column(Text)
    comments = Column(JSONB, nullable=False, default=list)
    total_tokens = Column(Integer, nullable=False)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    retrieval_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("repo_id", "pr_number", "diff_hash"),
    )
    repo = relationship("Repo", back_populates="reviews")


class Prompt(Base):
    __tablename__ = "prompts"

    hash = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    system_prompt = Column(Text, nullable=False)
    user_template = Column(Text, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt_hash = Column(Text, ForeignKey("prompts.hash"), nullable=False)
    model_version = Column(Text, nullable=False)
    dataset_version = Column(Text, nullable=False)
    security_precision = Column(Float)
    security_recall = Column(Float)
    security_f1 = Column(Float)
    bug_precision = Column(Float)
    bug_recall = Column(Float)
    bug_f1 = Column(Float)
    perf_precision = Column(Float)
    perf_recall = Column(Float)
    perf_f1 = Column(Float)
    style_precision = Column(Float)
    style_recall = Column(Float)
    style_f1 = Column(Float)
    overall_precision = Column(Float)
    overall_recall = Column(Float)
    overall_f1 = Column(Float)
    total_prs_evaluated = Column(Integer, nullable=False)
    avg_latency_ms = Column(Float)
    total_cost_usd = Column(Float)
    git_commit_sha = Column(Text)
    ci_run_url = Column(Text)
    notes = Column(Text)
    run_at = Column(DateTime, default=datetime.utcnow)


class CostLedger(Base):
    __tablename__ = "cost_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repos.id"), nullable=False)
    review_id = Column(UUID(as_uuid=True), ForeignKey("reviews.id"))
    model_version = Column(Text, nullable=False)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    cache_read_tokens = Column(Integer, nullable=False, default=0)
    cache_write_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Float, nullable=False)
    pipeline_step = Column(Text, nullable=False, default="review")
    created_at = Column(DateTime, default=datetime.utcnow)


class ReviewFeedback(Base):
    """
    Online feedback signal from developers acting on Sentinel's PR comments.

    Action vocabulary:
        dismissed     — developer dismissed the entire review (negative)
        resolved      — developer marked a single comment as resolved (positive)
        replied       — developer replied to a comment (engagement, neutral)
        thumbs_up     — developer reacted +1 (positive)
        thumbs_down   — developer reacted -1 (negative)
    """

    __tablename__ = "review_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id = Column(UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    comment_index = Column(Integer)  # index into Review.comments JSONB; null for review-level signals
    github_comment_id = Column(Text)  # GitHub PR review comment id (for dedupe)
    github_review_id = Column(Text)
    action = Column(Text, nullable=False)
    category = Column(Text)  # cached from Review.comments[i].category for fast aggregation
    severity = Column(Text)
    github_user = Column(Text)
    reply_body = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_review_feedback_review", "review_id"),
        Index("ix_review_feedback_repo_created", "repo_id", "created_at"),
        Index("ix_review_feedback_action", "action"),
        UniqueConstraint(
            "review_id", "github_comment_id", "action",
            name="uq_review_feedback_event",
        ),
    )


class RepoEmbedding(Base):
    __tablename__ = "repo_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(Text, nullable=False)
    chunk_type = Column(Text, nullable=False)
    chunk_text = Column(Text, nullable=False)
    start_line = Column(Integer)
    end_line = Column(Integer)
    embedding: Vector = Column(Vector(1024))
    # ``ts_content`` is maintained by Postgres so BM25 search needs no triggers.
    ts_content = Column(
        TSVECTOR,
        Computed("to_tsvector('english', chunk_text)", persisted=True),
    )
    last_commit_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("repo_id", "file_path", "chunk_type", "start_line",
                         name="uq_repo_chunk_location"),
        Index(
            "ix_repo_embeddings_embedding_ivfflat",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_repo_embeddings_ts_content_gin",
            "ts_content",
            postgresql_using="gin",
        ),
        Index(
            "ix_repo_embeddings_repo_recency",
            "repo_id",
            "last_commit_at",
        ),
    )
