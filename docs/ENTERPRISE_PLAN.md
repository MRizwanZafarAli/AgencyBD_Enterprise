# AgencyBD Enterprise: Analysis, Verification and Master Plan

Date: 2026-10-25. Scope: every module in the repository at commit `e4ad04a` plus the fixes made during this review.

## 1. Verdict

The platform is strong where it is evidence-based (auditors, hunt, radar, send-path guards, tenancy, secrets) and weak where the newest
"Autopilot" layer was added on top. That layer re-introduced invented data and bypasses guards the rest of the system enforces.
The UI is accurate in what it shows but too large: 19 screens plus 8 sub-tabs, all equal in weight.

| Area | State |
|---|---|
| Backend tests | 499 pass |
| Frontend | `tsc`, `oxlint`, `vite build` clean |
| All 19 UI screens | load with no console errors and no failed requests |
| Anonymous access | every API route returns 401 |
| Core flows (live) | Website Doctor, Local Hunt (OSM), Radar scan, SSRF block on loopback and metadata IPs: working |
| Autopilot | **Not trustworthy** (section 3) |

## 2. Fixed during this review

| # | Issue | Fix |
|---|---|---|
| F1 | **Live super-admin API key hard-coded** in `AuthGate.tsx`, `VisualGuide.tsx` and the user guide, committed and pushed to `origin/main` | Key revoked in the database; "1-Click Sign In" button, key display and guide text removed |
| F2 | `/api/system/updater/apply` let any `growth_lead` pull and run remote code, auto-push to GitHub and hot-reload | Super-admin only, disabled unless `AGENCYBD_ENABLE_UPDATER=on`, no auto-push by default; tested |
| F3 | Headed-browser launcher passed an unvalidated URL to Chrome (a value starting with `--` is a switch, e.g. `--renderer-cmd-prefix`) | Only SSRF-checked http(s) URLs accepted; tested |
| F4 | Headless-browser endpoints open to read-only roles | Require `pipeline:run` |
| F5 | CI workflow moved to `ci/ci.yml`, so GitHub Actions no longer ran | Restored to `.github/workflows/ci.yml` |

**Still required from you (cannot be done from here):** the revoked key remains in git history and on GitHub. Check whether the repository is
public; if it is, treat any data that key could reach as exposed. Rewriting history needs your explicit go-ahead.

## 3. Findings still open

### Critical / High

| ID | Finding | Evidence | Fix (phase) |
|---|---|---|---|
| A1 | **Autopilot fabricates facts and drafts false outreach.** Invented LCP (`3.2`/`3.4s`) and stack when the audit fails; "measured 3.4s" and "$2,880/mo" inserted into email subject and body; "Ran an architectural audit this morning"; "We deploy squads in 72 hours" | `orchestrator/autonomous_autopilot.py`; live run on a copy of your database | Rebuild on the real pipeline (P1) |
| A2 | **Invented contact:** every lead gets "Alex Founder" / "CTO" at a guessed `alex.founder@domain` (30% confidence) and is stored | same run | Use verified contacts only; otherwise create a task "find a decision maker" (P1) |
| A3 | **Guessed company domains.** SEC Form D filers become `<slug>.com`; many filers are funds or partnerships (e.g. "QP-Partnership II") that have no website | `agents/sourcing_agent.py:112` | Resolve through `CompanyResolver`, drop non-operating entities (P1) |
| A4 | **"P(Close) 94%" for a 30%-confidence guess.** Hand-picked weights presented as a Bayesian probability; expected pipeline ($122,200 for two leads) is not real | `engines/math_pipeline_engine.py` | Rename to a priority score; show probabilities only after calibration from your own outcomes (P1) |
| A5 | **Autopilot bypasses the guard chain.** It writes sequences as `queued_for_send` and sets the lead to `dispatched` with mock sender inboxes; nothing sends today, but the state is false and unsafe if a sender is attached | same file | Route through `OutreachSequenceWorkflow` (approval inbox, verification, suppression, policy) (P1) |
| A6 | **Second LLM gateway with a canned fallback.** `BrainGateway` "Tier 4 native expert brain" is a fixed script labelled as reasoning; bypasses cost logging and grounding | `engines/brain_gateway.py` | Delete; one gateway (`llm/client.py`) (P1) |
| A7 | **Headless Chrome SSRF is only checked on the first URL.** Redirects, sub-resources and DNS rebinding are not covered; `--no-sandbox` is set | `engines/native_browser_service.py` | Pinned-IP host rules or an egress-filtering proxy; drop `--no-sandbox` where possible (P2) |
| A8 | **Interactive browser does not perform clicks, typing or scrolling.** It re-renders the page and reports `action_executed` | `engines/interactive_browser_session.py` | Remove the claim or implement it with a real driver (P2) |
| A9 | **Evidence ledger is not tenant-scoped** and is file-based | `intel/evidence_ledger.py` | Store in the database with `org_id` (P2) |

### Medium

- Invented business inputs in the deck and differential tools: competitor defaults to `stripe.com`, visitors `40,000`/`50,000`, AOV `$120`/`$125`. Require user-entered values and label results "modeled with your inputs" (P1).
- Shared global state: interactive sessions default to `default_session` across tenants (P2).
- Tests encode the fabricated behaviour (`test_autonomous_autopilot.py` asserts `average_p_close_percent >= 50` on mocked leads). Replace with contract tests (P1).
- `.gitignore` does not cover `data/` runtime output (screenshots, evidence, sessions) (P0).
- Marketing text in the UI: "100% Autonomous", "$0.00 operating cost", "Claude-grade reasoning". Replace with factual status (P1).
- `app.py` (Streamlit, 1,321 lines) is legacy duplicate surface: retire (P3).

## 4. UI: from 19 screens to a task-first workspace

**Why it feels complex:** navigation lists every module (5 primary + 13 "specialized" + 8 tabs inside Autopilot), the Radar shows ~100 cards at once,
internal terms leak into labels ("Sovereign", "Swarm Pods", "Waterfall"), and the next step is never obvious.

**Principle:** the user's job is "find a client, understand them, approve outreach, win". Everything else is plumbing.

### Information architecture (4 surfaces)

| Surface | Purpose | Replaces |
|---|---|---|
| **Today** (default) | A single ranked inbox of what needs a human: approve this email, review this lead, reply to this message, fix this setup item. Each card has one primary action. | Autopilot, Mission Control, Approval inbox, Digest |
| **Find** | One search box with tabs by source: Local businesses · Jobs and projects · Tenders. Results as a compact ranked table with a detail drawer. | Local Client Hunt, Radar, Open Sourcing |
| **Clients** | One kanban plus a company page: brief, audit findings, evidence, contacts, drafts, history. | Website Doctor, Pipeline, Waterfall, Call Intel, Copy Coach, Video Studio |
| **Settings** | Setup checklist, services and portfolio, mailboxes and DNS, policy and autonomy, team and keys, API console. | 10 admin screens |

### Design rules

1. **One primary action per card.** Everything else lives behind "More".
2. **Autonomy dial** (Off, Suggest, Draft, Auto-send within limits) set once, shown as a single control; the policy engine already supports L0-L3.
3. **Progressive disclosure.** Tables show score, reason and next step; evidence and raw checks open in a drawer.
4. **Plain language.** "Hot lead" with a reason ("no website, 120 reviews") instead of "TIER_1_ENTERPRISE_ALPHA".
5. **Pagination and filters** on every list (the Radar must never render 100 cards).
6. **Honest empty and error states**, never placeholders. Keep the existing `ErrorBanner` contract.
7. **Setup wizard** for first run: identity, services, one case study, one source key. Reduces the 10-screen setup to one.
8. **Accessibility and performance:** keyboard-first (⌘K exists), WCAG AA contrast, table virtualization above 200 rows, reduced-motion respected.
9. **Design system:** keep Graphite & Signal tokens; document them as a component library (Table, Card, Drawer, Badge, Stat, EmptyState).

## 5. Issue-Finder agents (the "AI found a PHP bug" idea)

Context: reports describe two critical remote-code-execution flaws in PHP disclosed on 2026-10-21 (CVE-2026-109618 and CVE-2026-109619),
reportedly found with AI models. I could not verify the details against the PHP advisory; treat them as unconfirmed until you do.
Whatever the specifics, the product opportunity is real: **tell a prospect, with evidence, that something they run needs attention.**

### Rules (non-negotiable)

- **Passive only.** Public pages and standard requests; no exploit attempts, fuzzing, credential guessing or path brute-forcing.
- **Version-based findings are "potentially affected", not "vulnerable".** Each carries confidence and the exact signal (e.g. `Server: nginx/1.18` or a `generator` meta tag).
- **Responsible outreach.** For severe issues the message is a heads-up with the fix, not exploit detail, and never a threat. A policy gate blocks "critical vulnerability" wording unless the evidence is attached.
- **Every claim traceable** to an evidence row (existing ledger).

### Agent roster

| Agent | Checks | Sources (free where possible) |
|---|---|---|
| **Vulnerability Watch** | Fingerprint runtime/CMS/library versions from headers, meta tags, asset URLs; match to known CVEs | NVD API, OSV.dev, CISA KEV (actively exploited list) |
| **Exposure Check** | `security.txt`, `robots.txt` leaks, directory listing, exposed admin/login pages that are publicly linked, mixed content | public GET only |
| **Dependency Check** | Outdated or known-vulnerable JavaScript libraries and CMS plugins visible in page source | OSV.dev, retire.js dataset |
| **Hygiene Check** (exists) | TLS, headers, email auth (SPF/DKIM/DMARC), cookies | built |
| **Growth Check** (exists, extend) | SEO, structured data, performance, accessibility, AI-readiness (`llms.txt`, schema) | built |
| **Business Advisor** | Turns the evidence into 3 to 5 prioritized recommendations for the client's business, each citing evidence, with an estimated effort tier tied to your Services catalog | LLM through the grounded gateway; quotes or evidence ids required |
| **Competitor Compare** (exists, fix inputs) | Side-by-side technical comparison; revenue effect only from user-supplied traffic and AOV | built |

Outputs: a **Client Health Report** (one page, plain language), a prioritized fix list mapped to your services, and a draft outreach note held in the approval inbox.

## 6. Master backlog

Sizes: S under a day, M a few days, L about a week. Each item has an acceptance test.

### P0: Stop the bleeding (this week)
| # | Item | Size | Done when |
|---|---|---|---|
| 0.1 | Rewrite git history to remove the leaked key, force-push after your approval, rotate any key that ever shared a value | S | `git log -S` finds nothing |
| 0.2 | Gitignore `data/**` runtime output; add a secret-scan step to CI | S | CI fails on a planted key |
| 0.3 | Disable the Autopilot "Launch" and "queued_for_send" paths until P1 lands | S | no endpoint writes `queued_for_send` |
| 0.4 | Add `AGENCYBD_ENABLE_UPDATER` and the `--` URL guard to the security test suite | S | tests in place (done for two) |

### P1: Honest autopilot (weeks 1 to 2)
| # | Item | Size | Done when |
|---|---|---|---|
| 1.1 | Rebuild Autopilot as an orchestrator over existing, evidence-backed steps: source → resolve company → audit → brief → draft into approval inbox | L | no constant in the pipeline stands in for a measurement |
| 1.2 | Operating-company filter and domain resolution for SEC sources; drop funds, SPVs and unresolved names | M | the two sample filers are rejected |
| 1.3 | Contacts only from verified sources; otherwise create a "find a decision maker" task | M | no "Alex Founder" path remains |
| 1.4 | Replace P(Close) with a transparent priority score; add calibration from won/lost outcomes | M | UI labels it a score; probability appears only after N outcomes |
| 1.5 | Delete `BrainGateway`; route chat, objection triage and artifacts through `LLMGateway` with grounding | M | one provider path, costs logged |
| 1.6 | Require user inputs for deck and differential tools; remove default competitor and revenue figures | S | request without inputs returns 422 |
| 1.7 | Replace fabricated-behaviour tests with contract tests | M | suite asserts honesty rules |

### P2: Issue-Finder agents (weeks 2 to 4)
| # | Item | Size |
|---|---|---|
| 2.1 | Fingerprint → CVE matcher (NVD, OSV, KEV) with confidence and evidence rows | L |
| 2.2 | Exposure and dependency checks (passive) | M |
| 2.3 | Business Advisor with evidence-cited recommendations | M |
| 2.4 | Client Health Report (HTML and PDF) and severity-aware outreach policy gate | M |
| 2.5 | Harden the browser: pinned-IP or egress proxy, tenant-scoped sessions, ledger moved to the database | L |
| 2.6 | Nightly re-scan of saved clients; alert when a new CVE matches (a recurring reason to contact them) | M |

### P3: Enterprise UX (weeks 3 to 6)
| # | Item | Size |
|---|---|---|
| 3.1 | Today inbox and the four-surface navigation | L |
| 3.2 | Find: unified search with paginated table and detail drawer | L |
| 3.3 | Clients: company page and single kanban | L |
| 3.4 | First-run setup wizard | M |
| 3.5 | Component library, accessibility pass, table virtualization | M |
| 3.6 | Retire the Streamlit app and unused modules (Visual Guide diagrams become a short in-app tour) | S |

### P4: Scale and operations
| # | Item | Size |
|---|---|---|
| 4.1 | PostgreSQL with row-level security (needs Docker/Postgres available to test) | L |
| 4.2 | Observability: structured logs, metrics, alerting on bounces and scan failures | M |
| 4.3 | Backups tested by restore; staging environment; release process replacing the in-app updater | M |
| 4.4 | Load and soak tests for scanners and scheduler | M |
| 4.5 | Playwright end-to-end tests for the four surfaces | M |

## 7. Testing and acceptance

- **Honesty gates (CI):** no constant measurement in orchestrators, no person invented, no unverified claim in outbound text, scanner test for unsafe network calls (exists).
- **Security gates:** anonymous scan, role matrix test for every route, secret scan, SSRF suite including redirects.
- **UI gates:** Playwright smoke per surface, axe accessibility scan, no console errors, no request failures.
- **Definition of done:** feature + tests + empty/error states + docs + permission check.

## 8. Decisions needed from you

1. Approve rewriting git history to purge the leaked key (and confirm whether the GitHub repository is public).
2. Confirm the four-surface UI direction, or name screens you rely on daily that must stay.
3. Confirm Issue-Finder scope: passive only (recommended) and the outreach rule for severe findings.
4. Provide keys when ready: `GOOGLE_PLACES_API_KEY`, `ANTHROPIC_API_KEY`, and optionally an NVD API key (raises rate limits).
5. Confirm the in-app updater stays disabled in favour of a normal release process.


---

## Status (end of implementation)

| Phase | Result |
|---|---|
| P0 | Done. Key revoked and removed; scrubbed git history prepared but NOT pushed (needs your go-ahead); secret-scan test and CI job; CI restored |
| P1 | Done. Honest Discovery Run, verified domains, entity filter, transparent priority score, no invented contacts/prices/values, single LLM gateway, contract tests |
| P2 | Done. Vulnerability watch (NVD/OSV/KEV), exposure checks, Business Advisor, content guard, egress-filtered browser, tenant-scoped evidence, nightly re-scan, client report (HTML/PDF) |
| P3 | Done. Today / Find / Clients / Settings, setup checklist, background runs, WCAG AA (axe-verified), Streamlit and updater removed. Local map view was dropped in the rebuild |
| P4 | Done except PostgreSQL: request ids, metrics and alert rules, restore drill, release gate, load/soak tests, Playwright e2e. PostgreSQL is designed in `docs/POSTGRES_MIGRATION.md` and blocked on a Docker/Postgres environment |

Also fixed during this phase: per-thread pooled SQLite connections (two racing scheduler workers had stalled), and per-message workflow state is now thread-local.
