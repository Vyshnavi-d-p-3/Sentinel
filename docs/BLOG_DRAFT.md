# I built an AI code reviewer—and separated “demo” from “measurement”

*Draft for Medium / dev.to. Replace placeholder metrics with numbers from **your** runs. Add screenshots from **your** dashboard and CI.*

## Hook

Most LLM “code review” products optimize for a convincing UI. I wanted a system where **the evaluation story is as serious as the product story**: a fixed scoring pipeline, per-category P/R/F1, and automation that **fails the build** when a change silently degrades a category (e.g. security).

## What the repository actually is

- **Product:** A GitHub App–driven **FastAPI** service: diff ingest → **hybrid retrieval** (BM25 + pgvector, RRF) → **structured** review output (Pydantic) → cost accounting and optional GitHub Check Runs.
- **Dashboard:** **Next.js** pages for reviews, eval summaries, costs, prompts, and feedback—backed by the same API.
- **CI eval bundle:** **100 JSON fixtures** generated to line up with the **mock LLM** so continuous integration can exercise the full review path without API keys. That is a **stability and wiring** signal, not a claim about finding bugs in the wild.
- **Legacy fixtures:** A small set of **hand-authored** examples under `eval/fixtures/legacy/`. They are useful for illustration and for growing a real dataset; they are not presented as a complete benchmark.

**Precision for readers (and for you as the author):** do not describe the 100-PR CI set as “hand-labeled OSS PRs” unless you have actually performed that curation. The honest sentence is: *the harness is real; the default CI labels are mock-aligned synthetics; serious external validation requires a separate eval pass.*

## How measurement works (and what it is not)

- **Scoring** compares model comments to **human-written or fixture-defined** expectations using file path, line tolerance, and category—not “another LLM scoring the first LLM.”
- The **regression gate** compares strict per-category F1 to a **stored baseline** so prompt refactors do not erode one category in silence.
- **What this does *not* replace:** a prospectively defined, multi-repo, hand-labeled study. Building that is a **project of its own**; the repo provides the **machinery** (`eval_runner.py`, `labeling_rubric.md`).

## What I would report in v1 of the post

1. **CI:** Mock-mode eval + gate—what it guarantees (pipeline+scorer) vs what it does not (true recall on production traffic).
2. **Optional real-LLM run:** If you have keys and time, one **`eval_runner.py --no-mock`** pass on a small labeled slice, with model ID and cost noted.
3. **Operations:** HMAC webhooks, optional API key on dashboard routes, rate limits, idempotent webhook handling—enough to show you understand production, not just notebooks.

## Closing

The uncomfortable but useful takeaway: **a low, well-explained F1 on a real labeled set** is more valuable than a high number on a poorly specified benchmark. The codebase is set up to support that discipline; the **remaining work** is mostly **data and deployment**—see [`PUBLISHING_AND_BENCHMARK.md`](PUBLISHING_AND_BENCHMARK.md).

---
*End of draft. Delete this line before publishing.*
