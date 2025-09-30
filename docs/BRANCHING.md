# Git branching model

This repository follows a **Gitflow-inspired** layout used in many product teams: a long-lived integration branch, a production line, and short-lived feature work.

## Branches

| Branch | Role |
|--------|------|
| **`main`** | Default branch. Represents the **released, production-ready** line. Tags (e.g. `v1.0.0`) typically point at `main`. |
| **`production`** | Tracks what is **deployed to production** (or is fast-forwarded to match `main` after each release). Many teams alias this to `main`; keeping both is optional and useful when deployment pipelines target a dedicated ref. |
| **`develop`** | **Integration branch** for the next release. Feature branches merge here first; when a release is ready, `develop` merges into `main` (and `production` is updated). |

## Day-to-day workflow

1. Branch from **`develop`**: `feature/…`, `fix/…`, `chore/…`.
2. Open a pull request into **`develop`**; require review and CI green.
3. On release: merge **`develop` → `main`**, tag the release, then fast-forward **`production`** to `main` (or deploy from the tag).

## Protections (recommended on GitHub)

- **`main`** and **`production`**: require pull requests, status checks, no direct pushes.
- **`develop`**: require PRs or allow maintainers only.

## Recovery

If history is ever rewritten locally, a safety tag may exist: `backup/main-pre-redate` points at the pre-rewrite tip (see project maintainer notes).
