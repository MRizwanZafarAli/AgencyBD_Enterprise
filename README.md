# AgencyBD

Client and project hunting for a software agency. It finds prospects, checks their websites, scores them, and drafts outreach for
your approval. It will not invent a contact, a measurement, a result or a price: when something real is missing it creates a task for you.

## The app in six screens
| Screen | Use |
|---|---|
| **Today** | A focus list (top three things), week-over-week numbers, channel follow-ups, recent activity, then your inbox: approvals, tasks from automation, setup gaps. Start a **Discovery Run** here. |
| **Find** | One smart search box: describe what you want in plain words ("dentst in leeds without a website", "reakt developer remote over 5k"). It corrects spelling, understands business types, skills, places, budgets and filters, and says what it understood. Local businesses (Google Maps or free OpenStreetMap), jobs and projects, tenders. Every search field suggests as you type (typo-tolerant, keyboard friendly), and ⌘K accepts a whole sentence to search or log. |
| **Clients** | Pipeline board (search, sort, CSV export) and a page per client: audit, what to recommend, contacts, report, first-email draft, plus notes and follow-up tasks with a due date. Tasks due today or earlier appear on Today. |
| **Channels** | Type one sentence ("applied to react dashboard on upwork $1200 follow up friday") and confirm the draft. LinkedIn, Fiverr, Upwork, Freelancer.com, PeoplePerHour, Contra, Toptal, Guru: daily routine and streak, application pipeline with follow-up dates, message templates (LinkedIn 300-character counter), reply-time log, activity counters, working-hours reminders, profile checklist, saved links and search links. You work on each site in your own browser; this page is your tracker. Each tab also shows your funnel (reply, interview and win rate, cost per reply and per win), LinkedIn invite pacing over a rolling 7 days against your own limit, and a change log that comes due for review after 30 days. Each site tab also lists what the site offers with tips, jumps to its key pages, and shows weekly ratios (click rate, reply rate) from numbers you log. The **Browser dock** (sidebar) opens any of those pages in one window docked beside the app, in your own signed-in browser. It never logs in to, scrapes, refreshes or automates any of them, and stores no site passwords. |
| **Tools** | **Site Clinic** (paste a website, or a business and place: triage, examine, diagnose, a surgery plan you tick off, change since the last check, teardown, PDF report, save as client), searchable tool cards, and a site carries from one tool to the next. Also: compare two sites, client report, find an email, email draft checker, sequences, call notes, video script. |
| **Settings** | Setup checklist, services and proof, sending and policy, DNS, unsubscribe list, team and keys. |

**Look:** "Gilded Glass", golden yellow and white with Apple-style frosted glass, light by default with a warm graphite dark theme (toggle in the header). Colours are design tokens in `frontend/src/index.css`; contrast is checked by the accessibility e2e suite in both themes, and reduced-transparency settings get solid surfaces.

`Ctrl/⌘ + K` jumps anywhere. Keyboard: `G` then `T/F/C/H/O/S` switches screen, `[` collapses the sidebar, `?` lists every shortcut. **Stop sending** in the header halts every send, including scheduled ones.

## What it checks (passively; never intrusively)
Security headers, TLS, SEO, accessibility, AI-readiness, email DNS, exposure (security.txt, robots.txt leaks, open directory listings, cookie flags) and
**visible software versions matched against public vulnerability records** (NVD, OSV, CISA KEV). A version match is reported as *potentially affected*;
outreach about it is hedged and alarming wording is blocked.

## Keys and integrations
Add API keys in **Settings > Integrations and keys** (administrator only): Anthropic, Google Places, PageSpeed, Brave, NVD, GitHub, SAM.gov, email verifiers, Slack and more.
They are encrypted, never shown again, shared by the installation, and active immediately. Each row links to where to get the key and says what it costs. A key saved there overrides `.env`.

## Finding contacts
On a client page, **Find on their website** reads the company's own team, about and contact pages and lists the people (name with the job title shown next to it) and emails
they publish, each with its source page. Nothing is guessed. Saved contacts start unverified; only an email verification service can change that.

## Quick start
```bash
pip install -r requirements.txt
python3 scripts/generate_secrets.py          # writes strong secrets to .env
python3 scripts/create_admin_key.py          # prints your sign-in key once
cd frontend && npm ci && npm run build && cd ..
python3 -m uvicorn api:app --port 8001       # app + API at http://localhost:8001
```
For development run `npm run dev` in `frontend/` (port 5173, proxies to 8001). Docker: `docker compose up` (see `.env.example` for required variables).

## Configuration
Copy `.env.example` to `.env`. Nothing works "by default" with invented values: each feature reports **not configured** until its key exists.
Agency identity (name, sender, booking link, case study) comes from `AGENCYBD_*` variables; the case-study sentence is quoted to prospects verbatim, so keep it only if true.

## Tests
```bash
python3 -m pytest -q                         # ~520 backend tests
cd frontend && npx tsc -b && npx oxlint      # types and lint
./scripts/e2e.sh                             # Playwright + axe accessibility (uses your Chrome)
AGENCYBD_SOAK=1 python3 -m pytest tests/test_load_and_soak.py   # bigger load run
./scripts/release.sh                         # the release gate
```

## Security model
API keys are stored hashed; roles and tenant come from the credential, never from the request. All outbound fetches use an SSRF-safe client; headless Chrome runs behind an
egress filter proxy. Sending passes an ordered guard chain (jurisdiction, suppression, stop-on-reply, email verification, policy, content guard) and first touches wait for approval.
More in `docs/OPERATIONS.md`, `docs/ENTERPRISE_PLAN.md`, `docs/AUDIT_REPORT.md`.
