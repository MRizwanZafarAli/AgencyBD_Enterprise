# AgencyBD Enterprise: Product & Implementation Plan

*Written 2026-10-13 from (a) a full read of the current codebase and (b) web research on tools, platform rules, data sources and regulation. Statements marked ⚠ come from vendor blogs or could not be checked against a primary source. Verify them before spending money. Section 14 lists every open question.*

---

## Implementation status (updated 2026-10-13)

Built so far by Antigravity and then independently verified/fixed (see [AUDIT_REPORT.md](AUDIT_REPORT.md)).

| Area | State |
|---|---|
| Auth, RBAC, tenant scoping, secrets, signed unsubscribe, SSRF-safe fetching, fail-closed policy guards | **Done and tested** |
| Phase 1: Website Doctor (headers, SEO, GEO basics, a11y basics, evidence rows) | **Working**; missing real LCP/CLS (PageSpeed), axe-core, TLS, schema checks |
| Phase 1: Company resolver and briefs | **Not working yet** (does not resolve names; boilerplate briefs) |
| Phase 2: Radar (RemoteOK live, HN, SAM.gov, Upwork stub) | **Partly working**; HN picks wrong thread; Upwork needs OAuth |
| Phase 3: Proposal Studio + Approval Inbox | **Approval inbox works; proposal generation is a template** that cites demo case studies |
| Phase 4: Outbound (compliance, mailbox registry, sequence step) | **Building blocks only**; cannot truly send or verify; no scheduler |
| Phase 5: Policy engine, learning loop | **Policy engine fixed; not yet on the send path** |
| Phase 0 leftovers: Postgres, RLS, DEMO_MODE honoured everywhere | **Open** |

**Done since:** group 2 (no fabrication in real mode; verified, portfolio-grounded proposals; Portfolio UI). **Next:** group 3 (real email verifier, per-mailbox credentials, policy + approval on the send path).

---

## 0. The short version

**What you want:** one autonomous system for an agency that finds *every kind of work* (outbound prospects, freelance-marketplace jobs, public tenders, inbound signals), understands each opportunity like a senior human BD would, and acts on it: audits the prospect's web presence, explains the company to you, writes the pitch or proposal, sends it, handles replies, and learns from wins and losses.

**What the research says about "beat every tool":**

1. The autonomous-SDR category (11x, Artisan, etc.) is *not* a solved problem. Trade sources report 50–90 % churn within a year, and an A/B test reports human SDRs out-earning AI SDRs ⚠ (all vendor/competitor sourced; treat as directional). The consensus has moved to **hybrid: AI does the research and drafting, humans approve what matters**. A product that is *evidence-driven and governed* beats one that is merely *autonomous*.
2. The two channels you named have hard platform limits:
   * **LinkedIn** prohibits bots, scrapers and automation extensions in its [Help Center](https://www.linkedin.com/help/linkedin/answer/a1341387). It sued Proxycurl over scraping, and Proxycurl shut down in July 2025 under a permanent injunction ([overview](https://www.socialmediatoday.com/news/linkedin-wins-legal-case-data-scrapers-proxycurl/756101/)). **Do not build a LinkedIn scraper or auto-connect bot.** Section 4 shows how to deliver the same value legally.
   * **Upwork** shut its RSS feeds in Aug 2024 ([notice](https://support.upwork.com/hc/en-us/articles/52052528243731-RSS-deprecation)), defines bots as anything faster than a human, and does not allow auto-submission ([policy](https://support.upwork.com/hc/en-us/articles/43342677368467-Use-bots-and-other-automation-properly)). The *official* route is an approved API key with a read-only job-search scope ([developer portal](https://www.upwork.com/developer/documentation)). So: **discover via the API, draft with AI, a human presses Send.**
3. The biggest real differentiator available to you is **evidence**. Every claim in a pitch ("your LCP is 4.1 s", "you have no schema markup", "you are not mentioned by ChatGPT") must trace to a stored, timestamped measurement. Today the code *invents* contacts, audits and verifications; replacing that is job #1.

**Recommended positioning:** *"The BD operating system for agencies: finds work everywhere, proves why a prospect needs you, drafts the winning pitch, and only acts autonomously inside rules you set."*

---

## 1. Where the product is today (honest baseline)

Read from the code, not the README.

| Capability | State | Evidence |
|---|---|---|
| Sourcing (Maps, hiring, venture, LinkedIn) | **Simulated**, returns hardcoded companies | `agents/sourcing_agent.py`, `agents/linkedin_agent.py` |
| Contact enrichment | **Fabricated** names/emails with fake "250_OK" | `agents/enrichment_agent.py`, `agents/waterfall_enrichment.py` |
| Tech audit | Real fetch of homepage, but on any failure it **invents** metrics | `agents/tech_audit_agent.py` |
| Email dispatch | **Does not send**; flips a DB row | `agents/dispatch_agent.py` |
| CRM/Slack | Returns fake "SYNCED" | `agents/crm_relay_agent.py` |
| Reply triage | Keyword rules, works | `agents/objection_agent.py` |
| Copy scoring, spintax, SMTP probe, fingerprinter, DNS records, A/B bandit | **Real, reusable logic** | `engines/*`, `config/dns_fleet_configurator.py`, `analytics/` |
| Auth, RBAC, tenant scoping, secrets | **Done this session** (136 tests) | `security/`, `config/env.py`, `api.py` |
| UI | React (11 modules) + Streamlit; several tabs use static data | `frontend/`, `app.py` |
| Storage | SQLite; `leads.domain` and `decision_makers.email` are globally UNIQUE (blocks true multi-tenancy) | `database/db.py` |
| Orchestration | Synchronous method calls; no queue workers, no timers, no waits for replies | `orchestrator/swarm_engine.py`, `tasks/task_queue.py` |

**Rule for the whole roadmap:** nothing may return made-up data in a real run. Simulations move behind `DEMO_MODE=true`.

---

## 2. What a human BD person actually does, and where AI replaces each step

This is the spine of the product. Each step becomes an agent with a defined autonomy level (Section 7).

| # | Human step | What the human really does | System module | Default autonomy |
|---|---|---|---|---|
| 1 | Decide who to target | Picks industries/sizes/geos where services sell | **ICP & Service Playbooks** | Suggest → human approves |
| 2 | Find opportunities | Searches Maps, job boards, Upwork, tenders, news, communities | **Opportunity Radar** | Auto |
| 3 | Qualify | "Is this real, funded, reachable, a fit, worth my time?" | **Fit Scoring + Evidence** | Auto |
| 4 | Research the company | Reads site, news, LinkedIn page, reviews, jobs, stack | **Company Brief** | Auto |
| 5 | Research the person | Finds the right decision maker and their background | **Person Brief** | Auto (licensed data only) |
| 6 | Audit what they have | Checks site speed, SEO, security, UX, AI-readiness, tracking, content | **Website Doctor** | Auto |
| 7 | If no site / weak presence | Checks Google profile, socials, listings, domain | **Presence Rescue** | Auto |
| 8 | Pick the angle and offer | Matches findings to a service + proof (case study) | **Offer Composer** | Draft → approve |
| 9 | Write the outreach / proposal | Tailored email, LinkedIn note, marketplace proposal | **Proposal Studio** | Draft → approve |
| 10 | Send, follow up, rotate | Cadence over days, multiple channels | **Sequencer (durable workflows)** | Auto inside caps, after approval of the template |
| 11 | Handle replies | Answers, objections, "send info", unsubscribes | **Reply Agent** | Draft → approve; unsubscribes auto |
| 12 | Book and prepare | Calendar, prep brief, agenda | **Meeting Prep** | Auto |
| 13 | Propose, price, close | SOW, estimate, negotiation | **Deal Desk** | Human; AI assists |
| 14 | Learn | Why won/lost; adjust ICP and copy | **Learning Loop** | Auto reports |

---

## 3. Feature catalog (the "extraordinary" parts)

### 3.1 Company & Person Briefing Engine: *"I don't know this company or person"*

You said users often have only a company name and little knowledge. This is the answer. Input: a company name (or URL/domain). Output: a one-screen brief a non-expert can use on a call.

* **Who they are:** what they sell, to whom, size, location, age, funding, ownership, revenue band (labelled *estimated*, with method).
* **How they make money / how they work:** business model, customers, channels, pricing page, team structure from the About/Team pages.
* **Digital state:** site health, stack, tracking, SEO, AI-readiness (from Website Doctor).
* **Signals:** hiring (roles + age), funding, leadership change, tech change, press, review trend.
* **Who decides:** likely buyer titles for each service; named people only from licensed data or the company's own pages.
* **Pitch kit:** best angle, 3 talking points, objections to expect, what *not* to say, 2 relevant case studies from your portfolio, suggested offer and price band.
* **Confidence + sources:** every line links to its evidence (Section 8, `evidence` table). Lines without evidence are shown as "unverified" or omitted. The model is not allowed to guess.

### 3.2 Website Doctor: everything a human auditor would check

Run automatically; produces a prioritized, plain-language report plus a machine-readable score per category. Each check yields `{finding, severity, evidence, fix, estimated impact, service that fixes it}`.

| Category | Checks |
|---|---|
| **Performance** | Lighthouse via [PageSpeed Insights API](https://developers.google.com/speed/docs/insights/v5/get-started) (lab) **and** CrUX field data; LCP/INP/CLS, TTFB, page weight, render-blocking, image formats, caching, CDN |
| **SEO technical** | Indexability, robots.txt, sitemap, canonicals, redirects, broken links, hreflang, titles/meta/H1, duplicate content, internal linking, mobile friendliness, pagination |
| **SEO content/local** | Keyword targeting vs. services, thin pages, blog freshness, Google Business Profile completeness, NAP consistency, reviews volume/recency, local schema |
| **AI-readiness (GEO)** | Crawlable by AI bots (robots rules), `llms.txt` presence ⚠ *unproven lever, treat as low-cost extra*, schema.org (Organization, FAQ, Product, Article, LocalBusiness, BreadcrumbList), entity clarity, citable facts, brand mentions in ChatGPT/Perplexity/Gemini/Claude answers (sampled with fixed prompts, results cached and dated) |
| **Security** | HTTPS/HSTS, TLS config ([SSL Labs API v4](https://github.com/ssllabs/ssllabs-scan/blob/master/ssllabs-api-docs-v4.md), requires registration; non-commercial limits apply, so self-host `testssl.sh` for commercial use), CSP/X-Frame/X-Content-Type, mixed content, exposed admin paths, outdated CMS/plugins (versions from fingerprint), cookies flags |
| **Accessibility** | axe-core run in headless Chromium (WCAG 2.2 A/AA), contrast, alt text, labels, keyboard traps |
| **UX/conversion** | Primary CTA above fold, forms (count, friction), click-to-call, chat widget, pricing clarity, trust signals, mobile layout screenshots |
| **Tracking/stack** | GA4/GTM/pixels present, consent banner, CRM/forms, booking tools, e-commerce platform; own fingerprinter (`engines/native_tech_stack_fingerprinter.py`), optionally Wappalyzer ⚠ price unclear |
| **Email/domain health** | MX, SPF, DKIM, DMARC, domain age, expiry, lookalike domains |
| **Content & brand** | Last-updated signals, copyright year, outdated tech mentions, broken social links |

Implementation notes: use **Playwright** (headless) for rendering and screenshots, **never** to log into third-party sites. All fetches go through an SSRF-safe fetcher (Section 9). Results cached per (domain, check, 7 days).

### 3.3 Presence Rescue: businesses with *no website* or a weak one

A missing website is a *strong* lead, but it must be verified.

1. Discover candidates with Google Places **Text Search / Nearby (New)**. A missing `websiteUri` is a candidate signal only ⚠ (Google may simply lack it). Requesting `websiteUri` raises the SKU, so first filter on cheap fields, then call Place Details only for survivors ([pricing explainer](https://openplacesapi.com/blog/google-places-field-mask-pricing) ⚠). Read the [Maps Platform terms](https://cloud.google.com/maps-platform/terms) on **caching/storage limits** before persisting Places data (store `place_id` and re-fetch fields instead of keeping a copy).
2. **Verify "no site":** search by business name + city, check Facebook/Instagram/Yelp/Linktree/GBP "website" links, WHOIS/domain guess (`name.com`, `name.<cc>`), and Google results. Classify: `no_web_presence` / `social_only` / `directory_only` / `has_site`.
3. **Assess presence:** GBP completeness, reviews, photos, hours, categories, socials activity, competitors with sites in same area.
4. **Offer bundle:** site + GBP optimization + review generation + simple booking/AI-receptionist. Price band from your playbook.
5. **Outreach by phone/SMS/email where lawful**, plus a **printable/PDF "Digital Presence Report"** for door-knock or cold-call prep.

### 3.4 Opportunity Radar: every place work is posted

One normalized `opportunities` table (Section 8) fed by connectors. Compliance status is part of each connector's definition.

| Source | Access method | Rule / status |
|---|---|---|
| **Upwork** | Official GraphQL API (`api.upwork.com/graphql`), scope "Read marketplace Job Postings"; approved key required | Allowed *with approval*. No scraping. Drafts only, human submits. Cache ≤ 24 h per API terms ⚠ |
| **Freelancer.com** | Official API (OAuth2; sandbox available), project search; bid endpoint exists | Verify bid-via-API terms on [developers.freelancer.com](https://developers.freelancer.com) ⚠ (official docs not retrievable in research) before enabling any auto-bid; default human-approved |
| **RemoteOK** | Free JSON/RSS feed, no key; must credit and link back ([source](https://remoteok.featurebase.app/help/articles/3140840-is-there-an-api-or-rssjson-feed-of-remote-jobs)) | Allowed with attribution; mostly employment jobs (use for hiring-intent signals) |
| **We Work Remotely** | RSS per category | Allowed with attribution |
| **Hacker News "Who is hiring" / "Freelancer? Seeking freelancer?"** | Algolia + Firebase public APIs | Allowed; monthly threads |
| **Reddit** (r/forhire, r/startups) | Official API, OAuth, rate limits | Check current developer terms ⚠ |
| **Public tenders** | [SAM.gov Opportunities API](https://open.gsa.gov/api/opportunities-api) (free key; title-only keyword search; NAICS 541511/541512), [TED](https://ted.europa.eu) (CPV 72xxxxxx, free reuse), [UK Find a Tender](https://www.find-tender.service.gov.uk) (OCDS, Procurement Act 2023) | Public data; **big-ticket work** most agencies ignore |
| **Contra, Guru, PeoplePerHour, Toptal** | Verify per site | ⚠ Contra API unclear; no public listing APIs confirmed |
| **Fiverr** | No public listing API ([source](https://providers.apievangelist.com/providers/fiverr/)) | Skip; alerts by email only if you have an account |
| **Job-board aggregates** (Adzuna, Jooble, TheirStack ⚠) | Paid/free APIs | Hiring-intent signal: "company hiring 2 React devs for 40 days" → pitch a pod |
| **Funding/leadership/tech change** | Crustdata, Harmonic, Crunchbase ⚠ vendor claims | Signals, not intent proof; combine ≥2 |
| **LinkedIn** | **No scraping or automation.** See Section 4 | Restricted |

**Marketplace job pipeline** (Upwork/Freelancer): ingest → dedupe → **fit score** (skills match, budget vs your floor, client history: payment verified, spend, hire rate, location, proposals count) → **risk flags** (vague scope, off-platform requests, low budget, spam) → **Proposal Studio draft** (Section 3.5) → notification (Slack/email/push) → human reviews in the Approval Inbox → human clicks Send. Track Connects spent, reply rate, **cost per hire** (the metric that matters, not reply rate).

### 3.5 Proposal Studio

* **Inputs:** the opportunity text + your **portfolio library** (case studies, screenshots, metrics, tech, industries, testimonials, rate cards) embedded in pgvector.
* **Steps:** extract requirements → retrieve 2–3 closest case studies → decide pricing band → draft in the agency's voice → run a **self-critique pass** (does it answer the client's actual questions? any invented claims? length? platform rules?) → produce 2 variants for A/B.
* **Guardrails:** claims about the agency must come from the portfolio library (RAG with citations); claims about the client must come from the job post; no placeholders left; plagiarism/duplication check across your own proposals so you never send near-identical text to many clients (a spam signal on marketplaces).
* **Learning:** record outcome (viewed / replied / interview / hired / lost + reason) → feed the bandit and the retrieval ranking.
* Independent guides report raw AI proposals trail human-edited ones on reply rate ⚠, so the default flow is **AI draft + 60-second human edit**.

### 3.6 Reply Agent & Meeting Prep

Classifies replies (interested, objection type, out-of-office, wrong person, unsubscribe, hostile), drafts the answer using the objection playbook, and **auto-suppresses** unsubscribes immediately (all regions). Books via Cal.com/Google Calendar API, then generates a prep brief from the Company Brief + thread history.

### 3.7 Learning Loop

Weekly report: which signals, services, subject lines, case studies and platforms produced pipeline per dollar/hour; auto-proposed changes to the ICP and playbooks (human approves). This is the long-term moat: your own win/loss data.

### 3.8 Service Playbooks (so it works for *different kinds of work*)

A playbook = `{service, signals that indicate need, audit checks that prove need, offer, proof assets, price band, outreach angles, objection answers}`. Start with: web design/dev, e-commerce speed, SEO, AI integration/agents, mobile apps, cloud/DevOps modernization, data/BI, UI/UX, security hardening, WordPress/Shopify maintenance, accessibility compliance, local-business digital presence. New services = new playbook row, not new code.

---

## 4. "LinkedIn only gives me a company name": what to do legally

Facts: LinkedIn bans automation and scraping; the Proxycurl case shows enforcement against a *data provider*; whether scraping public pages is lawful is unsettled and fact-specific ([overview](https://nubela.co/blog/is-scraping-linkedin-legal-in-2026/) ⚠ written by the defendant). Account risk falls on **your** account.

**Design: never touch LinkedIn programmatically. Get the same value three other ways.**

1. **Company-name → brief, with no LinkedIn at all.** Resolve the name to a domain (search + Places + registries such as OpenCorporates ⚠), then run the Company Brief from the company's own site, news, job pages, funding and tech data. Most of the value users want ("what do they do, are they a fit, who runs it") comes from here.
2. **Licensed data vendors for people/company records** (they carry the compliance burden; ask for their sourcing and GDPR terms in writing): People Data Labs, Coresignal, Crustdata, Apollo ⚠ (prices and update cadence vary by source; I found no neutral compliance comparison). Wrap them behind one `PeopleDataProvider` interface so you can swap vendors.
3. **Human-in-the-loop "LinkedIn Companion"**: a *read-only side panel in your own UI* with (a) a one-click deep link to the company's LinkedIn page and a People search pre-filled with the right titles (the human clicks and reads), (b) a paste box: the user pastes a profile URL or text they are looking at, and the system generates the Person Brief and a connection note + message drafts to copy. **No bot, no extension, no automation on linkedin.com.** Optionally integrate Sales Navigator CRM Sync or a SNAP partner if you pay for Advanced Plus ([LinkedIn docs](https://business.linkedin.com/sell/sales-integrations)); partner-program availability is unclear ⚠.

---

## 5. Autonomy model: "fully autonomous" without becoming a spam cannon

Autonomy is a **policy**, not a switch. Every action type has a level per tenant.

| Level | Meaning | Examples |
|---|---|---|
| **L0 Observe** | Collect and score only | Radar ingestion, audits, briefs |
| **L1 Draft** | Prepare; human approves each item | Marketplace proposals, first emails to new segments |
| **L2 Guarded auto** | Act automatically **only if all guards pass** | Follow-ups in an approved sequence, replies to simple "send info", CRM updates |
| **L3 Delegated** | Auto within caps and kill-switch | Sending approved templates to verified contacts under daily caps |
| **Never auto** | Hard-coded | Upwork/Freelancer submit (until terms verified per platform), LinkedIn actions (none), anything priced > threshold, anything to unverified addresses, anything to suppressed/regulated regions without a recorded legal basis |

**Policy engine** (`policy/engine.py`): rules like `no_send_if(email_verification != 'verified')`, `max_per_inbox_per_day`, `no_send_if(country in blocked)`, `require_approval_if(deal_value > X or tier == enterprise)`, `halt_if(bounce_rate > 2% or spam_complaints > 0.1%)`. Every decision is logged with the rule that allowed/blocked it. The existing HITL gate and circuit breaker become instances of this engine.

---

## 6. Outbound deliverability & compliance (non-negotiable)

* **Sender rules:** Gmail and Yahoo require SPF, DKIM, DMARC and one-click unsubscribe for bulk senders, with spam rate **< 0.3 %** (target < 0.1 %); Gmail moved to SMTP-level rejections in late 2025 ⚠; Microsoft requires SPF/DKIM/DMARC (p=none minimum) for >5,000/day ([overview](https://redsift.com/guides/bulk-email-sender-requirements) ⚠ vendor). Even below the volume line, reputation matters. Cold campaigns routinely see 0.5–1 % complaints without list hygiene ⚠.
* **Law (verify with counsel for your markets):** US CAN-SPAM needs no prior consent for B2B but requires identity, address and opt-out; UK/EU allow corporate-subscriber outreach with a **documented legitimate-interest assessment**, role relevance, clear source disclosure and easy opt-out (Germany/Poland stricter); **Canada (CASL) is the highest risk**, so default **block Canada** unless implied consent is documented ([summary](https://bouncezero.io/cold-email-law-guide-2026) ⚠). The EU AI Act adds transparency duties for AI-generated outreach from Aug 2026 ⚠ unconfirmed.
* **Engineering requirements:**
  1. Per-country policy table (`allowed | needs_lia | blocked`).
  2. Store **data source + legal basis + timestamp** for every contact.
  3. Global suppression applies instantly, across tenants, to the *email and the domain* (keep the existing vault; add keyed hashing).
  4. Mandatory footer (identity, postal address, opt-out) and `List-Unsubscribe` + one-click POST header.
  5. Send through **real mailboxes on secondary domains** you control (Google Workspace/Microsoft 365). Google lists high system caps, but safe cold volume is far lower: ~25–50/day per warmed mailbox ⚠ vendor estimates. Use Smartlead/Instantly via API, or direct SMTP/Gmail API, behind one `SendProvider` interface.
  6. **Remove the "synthetic warmup network"** (`engines/native_warmup_engine.py`): faking engagement to inflate reputation violates ESP terms. Use organic ramp-up and a reputable warmup vendor if needed.
  7. **Email verification:** use a paid verifier API (ZeroBounce/NeverBounce/MillionVerifier ⚠ pick by price) as the gate. Own SMTP probing from a home IP is unreliable (port 25 blocked) and must **fail closed** (`unknown` ≠ `valid`).

---

## 7. Target architecture

```
                 ┌───────────────────────── React UI (Approval Inbox, Briefs, Radar, Studio) ─────────────────────────┐
                 │                                          FastAPI (auth, RBAC, tenants)                              │
                 └───────────────┬─────────────────────────────────────────────────────────────┬───────────────────────┘
                                 │                                                             │
                     Postgres 16 + pgvector  ◄── Alembic migrations                  Temporal (durable workflows)
          (opportunities, companies, people, evidence, audits,                    sequences, waits-for-reply, retries,
           proposals, approvals, events, policies, portfolio, runs)               timers, human-approval signals
                                 ▲                                                             │
                                 │                                                  Workers (Python activities)
                  ┌──────────────┴───────────────┐                         ┌───────────────────┼────────────────────┐
               Redis (cache,                Object storage              Connectors          Auditors            LLM agents
               rate limits)                 (screenshots, PDFs)       (Upwork, Freelancer,  (PSI, Playwright,   (Claude API: briefs,
                                                                        tenders, HN, Places,  axe, headers, TLS,   proposals, replies;
                                                                        data vendors, ESPs)   GEO probes)          structured outputs)
```

Choices and why:

* **Postgres + pgvector** replaces SQLite (concurrent workers, row-level tenant safety, vector search for portfolio RAG, JSONB for evidence). Use **SQLAlchemy 2 + Alembic**. Add `UNIQUE(org_id, domain)` and enable **row-level security** keyed on `org_id`.
* **Temporal** for durable multi-day sequences, "wait 3 days unless reply", approvals as signals, and crash-safe retries. Sources suggest Temporal for durability with the reasoning layer on top ([comparison](https://www.langchain.com/resources/langgraph-vs-temporal) ⚠ LangChain-authored). Keep LLM calls inside *activities* so non-determinism stays out of workflow code. *Simpler alternative if you want less infra at first:* a Postgres-backed queue (e.g. Procrastinate) + a `workflow_state` table; migrate to Temporal in Phase 4. Decide in Phase 0.
* **LLM layer:** Anthropic API (current IDs available in this environment: `claude-sonnet-5-5` default for drafting and analysis, `claude-haiku-5-5` for high-volume classification/triage, `claude-opus-5-5`/`claude-fable-5-1` for the hardest strategy briefs). Use **structured outputs/tool schemas** for every agent result, **prompt caching** for the large static prefix (portfolio, playbooks, style guide), and the **Batch API** for nightly audits and brief refreshes. Confirm current pricing and limits in the Anthropic docs before budgeting. Keep a **model gateway** (`llm/client.py`) so models are swappable and every call logs tokens, cost, latency, and prompt version to `agent_runs`.
* **Evidence-first generation:** agents may only use facts from `evidence` rows they are handed; a verifier step rejects drafts containing numbers or names not in evidence.
* **Observability:** keep Prometheus; add OpenTelemetry traces per opportunity; a cost ledger per tenant (the existing `financial_ledger`, now fed from real usage).
* **Security carry-over:** SSRF-safe fetcher (block private/link-local/metadata IPs, resolve-then-pin, redirect re-validation, size/time caps) for *every* outbound fetch of user-supplied domains; per-tenant rate limits; secrets in env/secret manager; audit trail immutable (append-only table + hash chain).

---

## 8. Data model additions (Postgres)

| Table | Key columns | Purpose |
|---|---|---|
| `companies` | `org_id, domain?, name, place_id?, size_band, country, industry, status` | Canonical company; domain nullable (no-website businesses) |
| `people` | `org_id, company_id, name, title, email?, email_status, source, legal_basis, collected_at` | Contacts with provenance |
| `opportunities` | `org_id, type (outbound/marketplace/tender/inbound), source, external_id, company_id?, title, description, budget_min/max, currency, posted_at, deadline, status, fit_score, risk_flags` | **One pipeline for all work** |
| `signals` | `company_id, type (hiring/funding/tech_change/leadership/…), payload, observed_at, source` | Timing triggers |
| `evidence` | `entity_type, entity_id, claim, value, source_url, method, observed_at, confidence` | **Every fact, with proof** |
| `audit_runs` / `audit_findings` | `company_id, category, check_id, severity, value, fix, est_impact, service_id, evidence_id` | Website Doctor output |
| `services` / `playbooks` | `org_id, name, signals, offer, price_band, objections, proof_assets` | Per-service plays |
| `portfolio_assets` | `org_id, title, industry, services, tech, metrics, body, embedding vector` | RAG for proposals |
| `proposals` | `opportunity_id, variant, body, status (draft/approved/sent/won/lost), model, prompt_version, outcome_reason` | Drafts + outcomes |
| `approvals` | `subject_type, subject_id, requested_by, decided_by, decision, reason, decided_at` | Human gate log |
| `outreach_messages` / `outreach_events` | `channel, thread_id, status, sent_at, opened/replied/bounced` | Sequencer state |
| `policies` / `policy_decisions` | `org_id, rule, level` / `rule, input, allowed, at` | Autonomy engine |
| `agent_runs` | `agent, model, prompt_version, tokens_in/out, cost_usd, latency, input_ref, output_ref, status` | Traces + cost |
| `consents` / `suppressions` | keyed hash + reason + region | Compliance |

---

## 9. Implementation plan: phases, exact changes, acceptance criteria

Estimates assume 1–2 engineers working with Claude Code; they are planning guesses, not commitments.

### Phase 0: Foundation (≈2 weeks)
**Goal:** a base on which nothing is fake.

| Change | Where |
|---|---|
| Postgres + Alembic + SQLAlchemy models; port existing tables; fix `UNIQUE(org_id, domain)`, `UNIQUE(org_id, email)`; RLS | new `db/` package; retire `database/db.py` raw SQL gradually |
| `DEMO_MODE` flag; move every hardcoded dataset to `demo/fixtures.py`; real runs raise `NotConfigured` instead of inventing | `agents/sourcing_agent.py`, `linkedin_agent.py`, `enrichment_agent.py`, `waterfall_enrichment.py`, `tech_audit_agent.py` fallbacks, `future_gtm_agent.py`, `adapters/vendor_connectors.py`, `crm_relay_agent.py` |
| SSRF-safe `net/fetcher.py`; use in site crawler, fingerprinter, audit, SMTP probe | `agents/site_crawler_agent.py`, `engines/native_*` |
| Connector framework: `connectors/base.py` (`Connector.fetch() -> list[Opportunity]`, `rate_limit`, `terms_url`, `automation_level`) | new |
| LLM gateway + eval harness (golden sets, regression gate in CI) | new `llm/`, `evals/` |
| Per-tenant rate limiting, login-failure throttling | `api.py`, `security/` |
| CI: Postgres service, migrations check, secret-scan | `.github/workflows/ci.yml` |

**Done when:** a fresh install with no API keys runs and every endpoint either returns real data or a clear "not configured"; tests run against Postgres; no module imports from `demo/` outside `DEMO_MODE`.

### Phase 1: Evidence engine: Website Doctor + Company Brief + Presence Rescue (≈4 weeks)
| Change | Where |
|---|---|
| `evidence` + `audit_*` tables and repositories | `db/models/`, `repos/` |
| Auditors: `auditors/performance.py` (PSI+CrUX), `seo.py`, `geo.py` (AI-readiness + sampled AI answer probes), `security.py` (headers, own TLS check), `a11y.py` (Playwright + axe-core), `ux.py`, `email_dns.py`, `stack.py` (reuse `native_tech_stack_fingerprinter`) | new `auditors/` |
| Report builder → JSON + HTML + PDF with plain-language "what this means" | `reports/` |
| Company resolver (name → domain/place/registry) and Company Brief agent | `intel/resolver.py`, `intel/company_brief.py` |
| Presence Rescue (Places + verification of "no site") | `intel/presence.py` |
| Replace `TechAuditAgent` internals with the auditors; keep its public method | `agents/tech_audit_agent.py` |
| API: `POST /api/companies/resolve`, `GET /api/companies/{id}/brief`, `POST /api/audits/run`, `GET /api/audits/{id}` | `api.py` → split into `routers/` |
| UI: **Brief page** and **Audit report page**; "Explain this company" box (name or URL) | `frontend/src/components/modules/` |

**Done when:** entering "Acme Plumbing, Austin" produces a brief where **every sentence has a source link**, a scored audit with ≥40 real checks, and, for a business without a site, a verified `no_web_presence` classification with the offer bundle. A hallucination eval (golden set of 30 companies) passes ≥95 % of claims traceable to evidence.

### Phase 2: Opportunity Radar (≈3 weeks)
| Change | Where |
|---|---|
| Connectors: `upwork.py` (GraphQL, OAuth, token refresh, backoff, 24 h cache cap), `freelancer.py`, `remoteok.py`, `wwr.py`, `hn.py`, `reddit.py`, `sam_gov.py`, `ted.py`, `uk_fts.py`, `adzuna/jooble.py`, `places.py` | `connectors/` |
| Normalizer + dedupe (URL, fuzzy title+company), fit scorer, risk flagger | `radar/` |
| Saved searches per tenant/service playbook; scheduler | `radar/schedules.py` (Temporal schedules or cron worker) |
| Notifications (Slack/email/push) | `notify/` |
| API: `/api/opportunities`, `/api/radar/searches` | `routers/radar.py` |
| UI: **Radar board** (filters: source, fit, budget, deadline, status), one-click "Draft proposal" | frontend |

**Prereq (you):** apply for the **Upwork API key** now (review covers account and use case; keep scope read-only job search) and register a Freelancer.com app. Both take calendar time.
**Done when:** ≥5 sources ingest on schedule, duplicates collapse, each item has a fit score and flags, and a tenant gets a Slack alert within 10 minutes of a matching post.

### Phase 3: Proposal Studio + Approval Inbox (≈3 weeks)
| Change | Where |
|---|---|
| Portfolio library (upload/import case studies; embeddings) | `portfolio/`, UI upload |
| Proposal agent (extract → retrieve → draft → critique → verify), 2 variants, similarity guard | `agents/proposal_agent.py` |
| **Approval Inbox**: queue of drafts with edit-in-place, diff vs. AI draft, "approve / edit / reject + reason" (reasons feed learning) | `routers/approvals.py`, UI |
| Outcome tracking (replied/interview/hired/lost) | `proposals` table + UI |
| Marketplace "assist" mode: copy-to-clipboard + deep link; **no automated submit** | UI |
| LinkedIn Companion panel (Section 4.3) | UI + `intel/person_brief.py` |

**Done when:** a human can go from Radar item to an approved, personalized proposal in < 3 minutes, and win/loss data is being captured.

### Phase 4: Real outbound engine (≈4 weeks)
| Change | Where |
|---|---|
| `SendProvider` (Gmail API / Microsoft Graph / SMTP / Smartlead/Instantly API) + mailbox registry (real inboxes, caps, health) | `outbound/providers/` |
| Verification gate via vendor API, fail-closed | `outbound/verify.py` |
| Temporal `OutreachSequence` workflow (steps, waits, stop-on-reply, business-hours/time-zone, jitter) | `workflows/sequence.py` |
| Inbound: IMAP/Gmail push/ESP webhooks → existing `InboundWebhookRouter` (now with tenant routing per mailbox) | `agents/inbound_webhook_router.py` |
| Reply Agent (classify → draft → approve or auto per policy) | `agents/reply_agent.py` |
| Compliance layer: country policy, footer + List-Unsubscribe, keyed suppression, LIA records | `compliance/` |
| Deliverability monitor: Google Postmaster Tools, bounce/complaint ingestion, auto-pause | rework `agents/deliverability_sentinel.py` (stop hardcoding `True`) |
| CRM: HubSpot/Pipedrive real sync | `adapters/` |
| Remove synthetic warmup engine | `engines/native_warmup_engine.py` |

**Done when:** a pilot of 3 mailboxes sends to verified contacts with bounce < 2 %, complaint < 0.1 %, every message has legal basis + source stored, unsubscribes take effect instantly.

### Phase 5: Autonomy, learning, analytics (≈3 weeks)
Policy engine (Section 5), autonomy settings UI, bandit over real outcomes (reuse `analytics/ab_testing_cohorts.py`), weekly Learning Report, cost-per-meeting and cost-per-hire dashboards, anomaly alerts, evals in CI.
**Done when:** a tenant can set a service to L2/L3 and the system acts only inside the policy; every action is explainable in the audit log.

### Phase 6: Enterprise hardening (ongoing)
SSO/SAML + SCIM, per-tenant encryption keys, data-retention + DSAR (erasure) tooling, SOC 2 readiness, billing/usage metering, backups/DR, load tests, white-label UI.

### Cross-cutting: cleanups already identified
* Split `api.py` (≈480 lines) into `routers/`; remove Streamlit once React reaches parity (keep it as an internal admin tool until then).
* Make the React tabs that use static data (`MissionControl`, `DnsStudio`, `CanSpamVault`, `EnterpriseRbac`, charts) read live endpoints.
* Replace the cosmetic tenant dropdown with the real tenant from `/api/auth/me`.
* Align Docker/nginx: serve the React build at `/`, API under `/api`, docs off in production.

---

## 10. Budget shape (order of magnitude, verify current prices)

| Item | Likely range | Note |
|---|---|---|
| Google Maps Platform | usage-based | Control with field masks and caching rules |
| PSI, HN, RemoteOK, WWR, SAM.gov, TED | free | Respect quotas and attribution |
| People/company data | ~$50–$5,000+/mo ⚠ | Wide spread across sources; start with the cheapest tier and measure hit rate |
| Email verification | per-check pennies | Gate is mandatory |
| Mailboxes + secondary domains | per mailbox/month | Scale with sending plan |
| Sending platform (if not building) | ~$40–$450/mo ⚠ | Instantly/Smartlead class |
| LLM | usage-based | Controlled by caching, Batch API and Haiku-class routing; log cost per opportunity |
| Infra | modest | Postgres, Redis, Temporal, small worker pool |

---

## 11. KPIs (what "beats the tools" must show)

* **Evidence rate:** % of claims in briefs/pitches backed by evidence (target ≥ 95 %).
* **Bounce < 2 %**, complaints < 0.1 %.
* **Time to first draft** from opportunity detection (< 10 min).
* **Approval edit-distance** (falls over time = the AI is learning the agency's voice).
* **Reply rate, meetings per 100 sends, cost per meeting, cost per hire** (marketplaces), pipeline $ per BD-hour saved.
* **False-positive rate** of "no website" and "missing AI/SEO" claims (target < 3 %).

---

## 12. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Marketplace/LinkedIn account bans | Lose channel | Official APIs only; human submit; no automation on LinkedIn; per-platform rule file reviewed quarterly |
| Hallucinated facts in outreach | Brand damage | Evidence-only generation + verifier + evals |
| Spam complaints / blacklisting | Lose domains | Policy engine, caps, verified-only, secondary domains, auto-pause |
| Legal (GDPR/CASL/CAN-SPAM) | Fines | Country policy, LIA records, suppression, counsel review before EU/UK/CA launch |
| Third-party data licensing | Cut-off or liability | Provider interface, written sourcing terms, store provenance |
| Google Places terms (storage) | Violation | Store `place_id` + re-fetch; legal read of terms |
| Cost blow-up (LLM/data) | Margin | Per-tenant budgets, caching, Batch API, cheap-model routing |
| Over-engineering | Delay | Ship Phase 1 + 2 + 3 as a human-in-the-loop product first; autonomy last |

---

## 13. Suggested build order if you want value fastest

1. **Phase 0** (foundation, no fake data).
2. **Phase 1** (Website Doctor + Company Brief + Presence Rescue): immediately useful to you even with no sending.
3. **Phase 2 + 3** (Radar + Proposal Studio + Approval Inbox): turns it into a daily work tool for marketplaces.
4. **Phase 4 → 5** (real outbound, then autonomy) once the evidence engine proves itself.

---

## 14. What I need from you to finalize

1. **Services you sell** and rough price bands (drives playbooks).
2. **Target markets** (countries/industries). This decides compliance (US/UK/EU/Canada).
3. **Platform accounts you already hold** (Upwork agency/Business Manager, Freelancer, Contra, LinkedIn plan) and whether you will apply for the Upwork API key now.
4. **Portfolio material**: case studies, metrics, testimonials, rates.
5. **Budget ceiling** for data vendors, mailboxes and LLM spend.
6. **Autonomy appetite**: confirm "AI drafts, human approves" for marketplaces and first-touch emails as the default.
7. **Team**: who reviews approvals daily, and who owns deliverability.

### Not verified in this research (check before relying)
Upwork ToS API clause text and current rate limits; Freelancer.com official endpoint list and bid-via-API terms; Reddit current API terms; Contra API scope; LinkedIn SNAP availability; Google Maps Platform storage clause; EU AI Act transparency timing; all churn/win-rate/price figures from vendor blogs.

---

## Sources

* Upwork: [bot/automation policy](https://support.upwork.com/hc/en-us/articles/43342677368467-Use-bots-and-other-automation-properly), [RSS deprecation](https://support.upwork.com/hc/en-us/articles/52052528243731-RSS-deprecation), [developer portal](https://www.upwork.com/developer/documentation), [GigRadar automation guide](https://gigradar.io/blog/upwork-ai-automation) ⚠, [Upwork AI policy summary](https://getmany.com/blog/upwork-ai-policy) ⚠
* LinkedIn: [prohibited software](https://www.linkedin.com/help/linkedin/answer/a1341387), [Proxycurl outcome](https://www.socialmediatoday.com/news/linkedin-wins-legal-case-data-scrapers-proxycurl/756101/), [Nubela write-up](https://nubela.co/blog/is-scraping-linkedin-legal-in-2026/) ⚠, [Sales Navigator integrations](https://business.linkedin.com/sell/sales-integrations)
* Market: [AI SDR comparison](https://www.amplemarket.com/blog/best-ai-sales-agents) ⚠, [AI SDR results](https://www.harborbd.com/blogs/ai-sdr-outbound-results-2026) ⚠, [GigRadar vs Vollna](https://tomba.io/blog/gigradar-alternatives) ⚠
* Data/sources: [SAM.gov Opportunities API](https://open.gsa.gov/api/opportunities-api), [Find a Tender API](https://www-tpp.find-tender.service.gov.uk/apidocumentation/api-how-to-guide), [RemoteOK API note](https://remoteok.featurebase.app/help/articles/3140840-is-there-an-api-or-rssjson-feed-of-remote-jobs), [WWR RSS](https://weworkremotely.com/remote-job-rss-feed), [Fiverr API status](https://providers.apievangelist.com/providers/fiverr/), [Places Insights sales leads](https://developers.google.com/maps/architecture/places-insights-sales-leads), [B2B data APIs](https://reply.io/blog/best-b2b-data-apis/) ⚠
* Audit tooling: [PSI API limits](https://unlighthouse.dev/learn-lighthouse/pagespeed-insights-api/rate-limits) ⚠, [SSL Labs API v4](https://github.com/ssllabs/ssllabs-scan/blob/master/ssllabs-api-docs-v4.md), [GEO tooling roundup](https://nogood.io/blog/generative-engine-optimization-tools/) ⚠
* Email: [bulk sender requirements](https://redsift.com/guides/bulk-email-sender-requirements) ⚠, [cold email law guide](https://bouncezero.io/cold-email-law-guide-2026) ⚠, [Google Workspace limits](https://mailreach.co/blog/google-workspace-email-sending-limits) ⚠
* Architecture: [LangGraph vs Temporal](https://www.langchain.com/resources/langgraph-vs-temporal) ⚠
