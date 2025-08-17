"""SQLAlchemy ORM models — repos, reviews, prompts, eval_runs, cost_ledger, embeddings."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, Text,
    ForeignKey, BigInteger, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

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
    cost_usd = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class RepoEmbedding(Base):
    __tablename__ = "repo_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(Text, nullable=False)
    chunk_type = Column(Text, nullable=False)
    chunk_text = Column(Text, nullable=False)
    start_line = Column(Integer)
    end_line = Column(Integer)
    embedding: Vector = Column(Vector(1536))
    updated_at = Column(DateTime, default=datetime.utcnow)
