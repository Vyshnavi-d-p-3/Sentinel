## Week 1: Foundation
- Struggled with pgvector installation on Apple Silicon — ended up using Docker for local dev
- Alembic + asyncpg conflict surprised me. psycopg2 required for migrations but not for runtime. Wasted 2 hours on this.

## Week 2: Retrieval
- First attempt at embedding search was embarrassingly slow (400ms per query). Turns out I forgot to create the IVFFlat index. With index: 12ms.
- BM25 tokenizer doesn't handle camelCase well. "validateSessionToken" needs to be split into "validate session token" for tsvector.

## Week 3: LLM Integration
- Biggest surprise: the model's confidence scores are not calibrated at all. 0.9 confidence comments are wrong just as often as 0.4. Built calibration buckets to prove this.
- Claude 3.5 Sonnet is 3x cheaper than GPT-4o for similar quality on code review. Made it the primary with GPT-4o as fallback.

## Week 4: Eval
- Labeling 98 fixtures took 35 hours, not the 15 I planned. The hard part is severity calibration — is MD5 for passwords "critical" or "high"?
- Clean PRs are harder to label than buggy ones. You have to prove a negative.

## Week 5-6: Dashboard + Iteration
- Prompt v2 improved security F1 by 3 points but doubled style false positives. This is when I built prompt versioning — can't iterate without measurement.

## Week 7: Production
- The httpx redirect bug (follow_redirects=False by default) cost me 30 minutes of debugging. Only manifests in production, not local dev.
- Neon uses ssl=require, not sslmode=require for asyncpg. Three driver-specific issues in one connection string.
