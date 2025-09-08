"use client";

import { useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { useReviews } from "@/hooks/reviews";
import { SeverityBadge, StatusBadge } from "@/components/badges";
import { EmptyState, ErrorPanel, LoadingBar } from "@/components/empty";
import { formatInt, formatRelativeTime } from "@/lib/format";
import type { ReviewListItem } from "@/lib/types";

const SEVERITY_OPTIONS = ["", "critical", "high", "medium", "low"] as const;
const CATEGORY_OPTIONS = [
  "",
  "security",
  "bug",
  "performance",
  "style",
  "suggestion",
] as const;
const STATUS_OPTIONS = ["", "completed", "skipped", "failed"] as const;

export default function ReviewsPage() {
  const [page, setPage] = useState(1);
  const [severity, setSeverity] = useState<string>("");
  const [category, setCategory] = useState<string>("");
  const [status, setStatus] = useState<string>("");

  const params = {
    page,
    per_page: 20,
    severity: severity || undefined,
    category: category || undefined,
    status: status || undefined,
  };

  const { data, isLoading, isError, error, isFetching } = useReviews(params);

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Reviews</h1>
          <p className="text-sm text-muted">
            PRs Sentinel has reviewed. Filter by severity, category, or status.
          </p>
        </div>
        {isFetching && !isLoading && <LoadingBar />}
      </header>

      <Filters
        severity={severity}
        setSeverity={(v) => {
          setPage(1);
          setSeverity(v);
        }}
        category={category}
        setCategory={(v) => {
          setPage(1);
          setCategory(v);
        }}
        status={status}
        setStatus={(v) => {
          setPage(1);
          setStatus(v);
        }}
      />

      {isError && <ErrorPanel error={error} />}

      {isLoading ? (
        <LoadingBar />
      ) : !data?.reviews.length ? (
        <EmptyState
          title="No reviews yet"
          description="Open a PR in a repo where Sentinel is installed, or POST to /webhook/github with a valid signature, and results will show up here."
        />
      ) : (
        <>
          <ReviewTable rows={data.reviews} />
          <Pagination
            page={page}
            perPage={data.per_page}
            total={data.total}
            onPage={setPage}
          />
        </>
      )}
    </div>
  );
}

function Filters(props: {
  severity: string;
  setSeverity: (v: string) => void;
  category: string;
  setCategory: (v: string) => void;
  status: string;
  setStatus: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-panel px-4 py-3">
      <Select
        label="Severity"
        value={props.severity}
        onChange={props.setSeverity}
        options={SEVERITY_OPTIONS.map((s) => ({ value: s, label: s || "any" }))}
      />
      <Select
        label="Category"
        value={props.category}
        onChange={props.setCategory}
        options={CATEGORY_OPTIONS.map((c) => ({ value: c, label: c || "any" }))}
      />
      <Select
        label="Status"
        value={props.status}
        onChange={props.setStatus}
        options={STATUS_OPTIONS.map((s) => ({ value: s, label: s || "any" }))}
      />
    </div>
  );
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="flex items-center gap-2 text-xs text-muted">
      <span className="uppercase tracking-wide">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-border bg-panel2 px-2 py-1 text-sm text-fg focus:outline-none focus:ring-1 focus:ring-accent"
      >
        {options.map((opt) => (
          <option key={opt.value || "any"} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function ReviewTable({ rows }: { rows: ReviewListItem[] }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-panel">
      <table className="w-full text-sm">
        <thead className="border-b border-border bg-panel2 text-left text-xs uppercase tracking-wide text-muted">
          <tr>
            <th className="px-4 py-2 font-medium">Repo · PR</th>
            <th className="px-4 py-2 font-medium">Title</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Worst</th>
            <th className="px-4 py-2 text-right font-medium">Comments</th>
            <th className="px-4 py-2 text-right font-medium">Score</th>
            <th className="px-4 py-2 text-right font-medium">When</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row) => (
            <tr
              key={row.id}
              className="transition-colors hover:bg-panel2/60"
            >
              <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">
                <Link
                  href={`/reviews/${row.id}`}
                  className="text-accent hover:underline"
                >
                  {row.repo_name || row.repo_id.slice(0, 8)}#{row.pr_number}
                </Link>
              </td>
              <td className="px-4 py-2 text-fg">
                <Link href={`/reviews/${row.id}`} className="hover:underline">
                  {row.pr_title || <span className="text-muted">(no title)</span>}
                </Link>
              </td>
              <td className="px-4 py-2">
                <StatusBadge status={row.status} />
              </td>
              <td className="px-4 py-2">
                <SeverityBadge severity={row.highest_severity} />
              </td>
              <td className="px-4 py-2 text-right font-mono text-xs text-muted">
                {formatInt(row.comment_count)}
              </td>
              <td className="px-4 py-2 text-right font-mono text-xs text-muted">
                {row.quality_score?.toFixed(1) ?? "—"}
              </td>
              <td className="whitespace-nowrap px-4 py-2 text-right text-xs text-muted">
                {formatRelativeTime(row.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Pagination({
  page,
  perPage,
  total,
  onPage,
}: {
  page: number;
  perPage: number;
  total: number;
  onPage: (n: number) => void;
}) {
  const lastPage = Math.max(1, Math.ceil(total / perPage));
  const from = total === 0 ? 0 : (page - 1) * perPage + 1;
  const to = Math.min(total, page * perPage);

  return (
    <div className="flex items-center justify-between text-xs text-muted">
      <span>
        Showing <span className="text-fg">{from}</span>–
        <span className="text-fg">{to}</span> of{" "}
        <span className="text-fg">{total}</span>
      </span>
      <div className="flex items-center gap-1">
        <PageButton disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Prev
        </PageButton>
        <span className="px-2">
          Page <span className="text-fg">{page}</span> / {lastPage}
        </span>
        <PageButton
          disabled={page >= lastPage}
          onClick={() => onPage(page + 1)}
        >
          Next
        </PageButton>
      </div>
    </div>
  );
}

function PageButton({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        "rounded border border-border px-2 py-1",
        disabled
          ? "cursor-not-allowed opacity-40"
          : "bg-panel2 hover:bg-panel hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}
