# Independent Verification of the "Phase 0–6 complete" Report

*2026-10-13. Every item below was tested against the code on disk (live server runs, anonymous-access scan of all 66 API operations, direct function calls, frontend build). Nothing here is taken from the report's own claims. Evidence commands are in the "How verified" column.*

## Status update (2026-10-13, after fix group 1)

| Item | Status | Verified by |
|---|---|---|
| P0-1 SSRF | **FIXED** | Live canary: 0 internal hits via fingerprint/crawl/audit/metadata IP; connect-time IP validation (covers redirects and DNS rebinding); SMTP probe validates MX; source-tree scanner test fails on any new raw network call |
| P0-5 Policy fails open | **FIXED** | Outbound guards now block on missing facts; suppression/jurisdiction looked up by the engine, not asserted by the caller |
| P0-7 Unsubscribe abuse | **FIXED** | Signed token (key derived from vault secret) verified; GET never changes state; POST one-click works; HTML-escaped; tenant bound to token. Also removed two hardcoded public salts (token + suppression hashing; legacy rows still honoured) and the hardcoded `agency.example.com` link |
| P0-8 UI auth | **FIXED** | Both pages use `apiFetch`; test fails on any bare `fetch(` in `frontend/src` |
| P0-2 Fabrication in real mode | **FIXED** | `config/honesty.py` contract; sourcing, LinkedIn, enrichment, waterfall, visitor ID, vendor fallbacks, CRM/Slack, dispatch, dossier, copy, radar, LLM canned fallback all return `not_configured`/empty/unreachable outside DEMO_MODE; tests run in real mode by default |
| P0-3 Proposal Studio | **FIXED** | Real portfolio library (tenant-scoped, TF-IDF retrieval); LLM-generated variants; `proposals/verifier.py` rejects unsupported figures and unbacked past-work claims; one retry; only verified drafts reach the inbox; stored job text used, not caller text. Needs `ANTHROPIC_API_KEY` to run for real (tested with a stubbed model only) |
| Also fixed | | Unreachable site now = status `unreachable`, no score; SMTP/waterfall unknown never reads valid; real SPF/DKIM/DMARC DNS checks; opportunity scans idempotent; approval decide is tenant-scoped; P1-6 cross-tenant proposal id |
| P0-4, P0-6 | Open | Fix group 3 |
| P1 / P2 | Open | Fix groups 4 and 5 |

Tests: **229 pass** (group 2 added 44; group 1 earlier: 185) (152 before + 33 new in `tests/test_group1_security_fixes.py`). Anonymous scan: 61 of 66 operations return 401; the 5 others are the three health probes and the signed-link unsubscribe endpoint (400 without a valid token).

Known leftover from group 1: when a domain is simply *unreachable* (not blocked), `agents/tech_audit_agent.py` still falls back to invented metrics. That is P0-2 and is next.

## Verdict

**Solid foundation, not yet "complete".** Authentication, tenant isolation of core data, the evidence-backed Website Doctor, live Radar ingestion and the compliance building blocks are real and working. But the system still **fabricates data in real mode in several places, has a working SSRF hole, cannot actually send email or verify addresses, and two flagship UI pages cannot authenticate.** Do not point it at real prospects until the P0 items are fixed.

**Test status:** 152 / 152 pass; `tsc` clean; Vite build passes; `oxlint` 2 warnings (React effect style). Passing tests did not catch any of the problems below, so the tests are checking presence, not truth.

## What is verified working

| Claim | How verified | Result |
|---|---|---|
| Every API route requires auth | Anonymous call to all 66 OpenAPI operations | 61 return 401. The 5 open ones: `/healthz/live`, `/healthz/ready`, `/api/health`, and `GET`+`POST /api/compliance/unsubscribe` |
| Website Doctor produces real findings with stored proof | Audited `example.com` and `www.python.org` live | Real findings across performance, security, SEO, GEO, a11y; **18/18 findings have an `evidence` row** with measured value, URL and method |
| Audit results are tenant-isolated | Tenant B read tenant A's audit | 0 findings visible |
| Radar ingests real data | `POST /api/radar/scan` with no credentials | Pulled live RemoteOK jobs; stored 13 normalized opportunities |
| New SSRF client blocks internal targets | `POST /api/audits/run {domain:"127.0.0.1:9999"}` | Blocked ("Security Policy Block") |
| Company briefs isolated per tenant | Tenant B fetched tenant A's brief | 404 |
| 25-table schema with `UNIQUE(org_id, domain)` | Code read + tests | Present (SQLite, not Postgres; no row-level security) |
| Secrets, auth, tests-on-temp-DB from the previous phase | Re-ran | Still intact |

## Findings

### P0: fix before any real use

| # | Finding | Evidence | Fix |
|---|---|---|---|
| **P0-1** | **SSRF still open on legacy endpoints.** `/api/native/fingerprint_tech` fetched a loopback service and returned its content (detected "WordPress" from the canary page). Others still use raw `requests`/sockets: `engines/native_tech_stack_fingerprinter.py`, `agents/tech_audit_agent.py`, `agents/site_crawler_agent.py`, `agents/linkedin_agent.py`, `agents/sourcing_agent.py`, `engines/native_smtp_verifier.py` (raw sockets), `adapters/vendor_connectors.py` (fixed hosts, OK) | Canary server on `127.0.0.1:9999` recorded a request from the fingerprinter | Route **every** user-influenced fetch through `net/fetcher.py`; for SMTP probing resolve MX then validate IPs with the same blocklist; add a test that scans the source tree and fails on `requests.`/`urllib.request`/`socket.` outside `net/` and an allow-list of fixed vendor hosts |
| **P0-2** | **Real mode still fabricates.** With `DEMO_MODE` unset, `POST /api/sourcing/run` returned hardcoded "Kinetix BioSciences" etc. as success. `radar/engine.py` seeds `DEMO_OPPORTUNITIES` when nothing is ingested. `portfolio/library.py` serves `DEMO_PORTFOLIO_ASSETS` | Live call; code read | Only load fixtures when `settings.demo_mode`; otherwise return `{"status":"not_configured"}` or an empty list. Remove the "seamlessly incorporates demo fixtures" fallback. Also audit `linkedin_agent`, `future_gtm_agent`, `enrichment_agent`, `waterfall_enrichment`, `tech_audit_agent` fallbacks the same way |
| **P0-3** | **Proposal Studio invents past performance.** In real mode it cites "FinTech Core Modernization for Global Payroll Scaleup" and "reduced Core Web Vitals latency by 74%" (from demo fixtures); ignores the job post; **variant A and B bodies are identical**; `model: "deterministic-rules"` | `POST /api/proposals/draft` | Require real `portfolio_assets` rows (return `portfolio_empty` error otherwise). Generate from the opportunity text via the LLM gateway with structured output, then run a verifier that rejects any metric/name not in retrieved assets or the job text. Variants must differ meaningfully. Add golden-set eval |
| **P0-4** | **Outbound send bypasses policy and approval.** `OutreachSequenceWorkflow.execute_step` and `/api/outbound/sequence/step` never call `PolicyEngine`. Only `routers/policy.py` uses it. Any user with `pipeline:run` can send any text to any verified address with no L1 approval | `grep PolicyEngine` | Call `PolicyEngine.evaluate("outbound_first_touch"/"outbound_followup", ctx)` **inside** `execute_step` with context computed server-side (verification, suppression, jurisdiction, deal value). If `requires_human_approval`, create an `approvals` row and return `pending_approval`; only the approve action sends |
| **P0-5** | **Policy engine fails open on missing context.** `is_suppressed` blocks only if `== True`; `jurisdiction_allowed` blocks only if `== False`. A caller that omits them passes | `policy/engine.py` | Treat missing/`None` as blocked (`is not True` for allowed flags). Compute these inside the engine from DB, not from the caller |
| **P0-6** | **Real sending and verification are impossible.** `Settings` has no `smtp_*` or `zerobounce_api_key` fields, so `getattr(settings, ..., None)` is always `None` → `SmtpProvider` is never configured and the gate can never return `verified` outside demo mode. In demo mode both fake success. The vendor branch in `EmailVerificationGate.verify` (`if self.api_key:` → returns "verified" with comment "simulate valid API call") **never calls a vendor**; it would approve every address the moment a key is set. SMTP uses **one global account** for all mailboxes (no per-mailbox credentials), so rotation is cosmetic | Settings read; function call | Add settings fields; implement a real verifier client (ZeroBounce/NeverBounce/MillionVerifier) with timeout, result mapping (`valid/invalid/catch-all/unknown`; only `valid` passes) and caching; use MX lookup (`dnspython`), not `gethostbyname`. Store per-mailbox credentials **encrypted** (new `mailbox_credentials`, Fernet/KMS key from env), and select provider per mailbox. Delete the fake-success branch |
| **P0-7** | **Public unsubscribe can be abused.** Anyone can anonymously suppress any email for any `org_id`, and suppression is global, so an attacker can wipe your prospect list. The `token` parameter is never checked | Called it anonymously; email became suppressed for tenants A and B | Generate an HMAC token per (org, email, message id) in `compliance/footer.py` and **verify it** on `/unsubscribe`; ignore caller-supplied `org_id` (take it from the token). Keep RFC 8058 `POST` one-click working with the same token |
| **P0-8** | **Website Doctor and Opportunity Radar pages cannot authenticate.** `WebsiteDoctor.tsx` and `OpportunityRadar.tsx` use plain `fetch` (no `X-API-Key`), so every call returns 401 in the browser | grep; routes are locked | Replace `fetch(` with `apiFetch(` (import from `lib/api`); add a test/lint rule forbidding bare `fetch('/api` in `frontend/src` |

### P1: correctness and honesty

| # | Finding | Fix |
|---|---|---|
| P1-1 | **Company resolver doesn't resolve.** "Stripe" and "Zxqv Plumbing Holdings" both return `status:"resolved"` with `domain:null`. Briefs then say "operates digital infrastructure at unassigned domain", "Identified 0 immediate technical enhancements on None", health score **85 with 0 evidence** | Resolver must return `unresolved` when no domain is found. Implement candidate search (web search API or Places) + domain verification (fetch homepage, match company name). Brief must refuse to score without audit evidence; every sentence needs an `evidence_id` or is omitted |
| P1-2 | **Brief claims "every sentence links to proof"**: `evidence_count: 0` | Enforce in code: drop unsupported sentences; add eval |
| P1-3 | **Website Doctor lacks the headline metrics.** No LCP/CLS/INP (no PageSpeed API, no Playwright), no `axe-core`, no TLS inspection, no schema.org validation. The report claims "Real TTFB, LCP, CLS"; only response time and header checks exist | Add PSI API (lab+CrUX) with key and backoff; Playwright + axe-core for a11y/screenshots; TLS via stdlib `ssl` or testssl.sh; JSON-LD parsing for schema |
| P1-4 | **HN connector selects the wrong thread** ("Who is hiring? (February 2017)"): relevance search with `hitsPerPage=3` | Use `search_by_date`, filter author `whoishiring`, pick newest title matching the month; also pull the "Freelancer? Seeking freelancer?" thread |
| P1-5 | **Sequence engine is a single-step function, not a workflow.** `delay_days` and the 7–18 min jitter are computed but never applied; nothing schedules step 2/3. **Stop-on-reply query is wrong**: it joins `inbound_replies`→`leads` and compares `LOWER(company_name)` to an **email**, so that branch never matches (only the `outreach_events` branch works) | Persist a `sequences`/`sequence_enrollments` table with `next_run_at`; add a worker loop (or Temporal) that executes due steps; fix the reply check by joining on `decision_makers.email` / thread id; apply jitter via `next_run_at` |
| P1-6 | **Cross-tenant references.** `POST /api/proposals/draft` accepted another tenant's `opportunity_id` (stored under the caller's org) | Verify the opportunity belongs to the caller's org (404 otherwise) in every router that takes a foreign id |
| P1-7 | **Upwork connector** reads a static `UPWORK_API_TOKEN` env var; no OAuth2 flow/refresh, no scope handling, not testable without credentials | Implement OAuth2 authorization-code flow + refresh (tokens encrypted per tenant); add recorded-response tests (VCR) so it is verifiable offline |
| P1-8 | **Webhook org attribution is global** (`AGENCYBD_WEBHOOK_ORG_ID`), and inbound replies don't set `outreach_events` consistently across mailboxes | Route by mailbox/`Message-ID` → tenant; one signing secret per tenant |

### P2: quality

* Tests assert existence, not truth. Add: a **no-fabrication test suite** (runs everything with `DEMO_MODE` off and asserts no demo strings appear), a **golden eval set** for briefs/proposals, a **source-tree SSRF scanner**, and a **UI contract test** that every `fetch` carries auth.
* SQLite remains the only store (no Postgres, no RLS). Acceptable for a pilot; required for multi-tenant production.
* `oxlint`: 2 `set-state-in-effect` warnings (`OpportunityRadar.tsx:34`, `GovernanceAndLearning.tsx:87`).
* Report wording to correct: "multi-step cadences orchestrated", "dual variants for A/B", "Smartlead provider verified", "real LCP/CLS", "every sentence links to proof", "SSRF-safe network client" (new client only).

## Prioritized fix order (hand this to Antigravity one item at a time)

1. P0-8 (UI auth), P0-7 (unsubscribe token), P0-5 (policy fail-closed), P0-1 (SSRF sweep + scanner test).
2. P0-2 + P0-3 (remove fabrication; real proposal generation with verifier).
3. P0-6 (real verifier + per-mailbox credentials + settings), P0-4 (policy/approval on send path).
4. P1-1/P1-2 (resolver + evidence-enforced briefs), P1-3 (real performance/a11y/TLS/schema), P1-4, P1-5, P1-6, P1-7.
5. Postgres + RLS, workers/scheduler, per-tenant webhook secrets.

**Definition of done for each fix:** a failing test first that reproduces the finding (use the evidence column), then the change, then the full suite green, plus the anonymous-access scan still showing only the allow-listed open routes.

---

## Final status (all groups complete)

| Group | Scope | Status |
|---|---|---|
| 1 | Auth, secrets, tenant scoping, SSRF, webhooks (P0-1/5/7/8) | Done, tested |
| 2 | Honesty contract, proposal grounding (P0-2/3) | Done, tested |
| 3 | Send path: guard chain, drafts/approval, caps, SMTP, verification, scheduler | Done, tested |
| 4 | Intelligence: resolver, brief, auditors, presence, radar connectors | Done; connectors validated against live HN/RemoteOK/WWR/TED/UK FTS |
| 5 | Learning loop, per-tenant webhooks, cost accounting | Done, tested |
| Final | Fabricated content removed from agents/UI; agency identity is env-driven; backup script; worker + backup services; CI frontend job | Done |

**Verified here:** 433 backend tests; frontend `tsc`, `oxlint`, `vite build`.

**Not verifiable without credentials or infrastructure:**
- Real LLM proposal generation (needs `ANTHROPIC_API_KEY`; tested with stubs).
- SAM.gov and Upwork GraphQL response shapes (no keys).
- Real SMTP and email-verification vendors (stubbed).
- DKIM/DNS setup for sending domains.

**Deliberately deferred:**
- Postgres + row-level security: large rewrite that cannot be tested while the Docker daemon is down. SQLite (WAL) with application-level tenant scoping is the current model.
- Streamlit app is a legacy lab; the React frontend is the product UI.

**Operator follow-ups:** review/revoke ~35 stray API-key rows in the real `data/agency_bd.db`; fill the agency identity variables in `.env`; nothing is committed to git yet.


---

## Addendum: hunting features and UI (2026-10-13)

- **Local Client Hunt** (`intel/local_hunt.py`, `POST /api/hunt/local`): Google Places (needs key) or free OpenStreetMap search; each business is classified from real checks (no website, social-only, dead domain, certificate error, working site with measured issues) and ranked by a transparent win score. A site that blocks bots (HTTP 403) is reported as "not assessed", never "down". OSM absence is flagged "verify before pitching".
- **New sources:** Reddit r/forhire `[HIRING]` posts and GitHub bounty issues with a stated dollar reward (parsers tested on recorded live responses).
- **Grounded LLM reasoning** (`llm/reasoning.py`): go/no-go on a job and a brief summary. Points without an exact quote from the job post, and sentences without valid evidence ids, are dropped. Needs `ANTHROPIC_API_KEY`; tested with a stubbed model only.
- **Digest** (`workflows/digest.py`, `scripts/send_digest.py`): top opportunities and untouched local leads; Slack needs `SLACK_WEBHOOK_URL`.
- **Real kill switch** (`workflows/controls.py`, `/api/controls/outbound`): per tenant, blocks manual and scheduled sends, pauses without losing sequence state. The old header button was cosmetic.
- **Fixed:** `GET /api/opportunities` no longer scans the internet as a side effect.
- **UI:** "Graphite & Signal" theme (Inter + JetBrains Mono, one indigo accent), page and card animations that respect reduced-motion, skeleton loaders, command palette (Cmd/Ctrl+K), header status measured from `/healthz/live` (the old latency and "DNS pool" figures were hard-coded), fake tenants and real-person sample data removed.
