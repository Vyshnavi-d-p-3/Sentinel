# Demo video outline (~3–4 minutes, Loom / YouTube)

**Goal:** Show a working system *and* speak accurately about what the eval numbers mean. Script what you will say; do not improvise the distinction between “CI / mock” and “real-LLM / hand-labeled” under time pressure.

## Segments

1. **Title (10s)**  
   *“Sentinel: code review with a regression-gated eval harness”*

2. **Problem (20s)**  
   Thin wrappers are easy; **measurement** is hard. One sentence: you want to know if changes **break** security or bug detection—not just if the model still returns JSON.

3. **Architecture (35s)**  
   One visual: GitHub → webhook (HMAC) → orchestrator → retrieval (BM25 + dense + RRF) → LLM gateway → structured output / costs. No deep dive.

4. **Live: review path (40s)**  
   Prefer **your deployed** API or `docker compose` on localhost. If using **mock mode**, say it once: *“This environment is using deterministic mock inference so we’re not spending tokens.”*  
   If showing a real GitHub flow: test repo, PR, Check Run or comment—only what you can reproduce.

5. **Dashboard: Reviews + health (30s)**  
   Open `Reviews` (may be empty in a fresh DB—say that). Show `/health` or the home health card: DB + LLM status.

6. **Eval page (50s) — be precise**  
   - If numbers come from **synthetic+mock** CI: *“These metrics regression-test the scoring pipeline; they’re not a claim about production bug-finding F1.”*  
   - If you have **disk/DB** results from a real-LLM run, say the **model** and that labels were from **your** fixture set.  
   - Point at **per-category** F1 and mention the **CI gate** in GitHub Actions.

7. **Costs or settings (20s)**  
   Token budgets or cost summary; reinforces production awareness.

8. **Close (15s)**  
   Repo link, point to `docs/PUBLISHING_AND_BENCHMARK.md` for *deploy + real benchmark* work, CTA to read the blog draft.

## Recording hygiene

- 1080p, single browser window, **no** scrolling through unrelated tabs.  
- Rehearse segment 6 once so eval claims stay accurate.  
- If anything fails live, keep a **short screen recording** of a green path and splice—or record voiceover on static screenshots. Honest delivery beats a faked “everything works in prod” if your stack is still local-only.

**Outside the repo:** posting the file to Loom/YouTube and embedding in README or blog is a publishing step, not a code change.
