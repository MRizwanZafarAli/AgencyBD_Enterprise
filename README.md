# ⚡ AgencyBD_Enterprise: Autonomous Multi-Agent BD Swarm

Enterprise-grade autonomous Business Development & Lead Intelligence platform engineered for software and AI development agencies. Completely replaces human SDR/BDR overhead with trigger-led, audit-driven multi-agent intelligence.

---

## 🏛️ System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   APEXCORE AUTONOMOUS BD AGENT SWARM                   │
├────────────────────┬───────────────────────────────────────────────────┤
│ Micro-Agent        │ Core Functional Responsibility                    │
├────────────────────┼───────────────────────────────────────────────────┤
│ 1. SourcingAgent   │ Google Maps local B2B, JobSpy hiring signals,     │
│                    │ and venture database ingestion.                   │
│ 2. TechAuditAgent  │ Automated DOM, TTFB, Lighthouse LCP, and tech     │
│                    │ stack fingerprinting (WordPress, Next.js, etc.).  │
│ 3. EnrichmentAgent │ CTO / Founder discovery & DNS MX socket SMTP      │
│                    │ handshake verification (0% bounce rate).          │
│ 4. DossierAgent    │ Executive pain point mapping & Loom script concept│
│ 5. CopywriterAgent │ Trigger-based 3-step sequence & LinkedIn pitches  │
│                    │ with spam friction score guardrails (< 80 words). │
│ 6. DispatchAgent   │ Secondary sending domain rotation & daily quotas. │
│ 7. ObjectionAgent  │ Inbound sentiment triage & automated rebuttals.   │
│ 8. BookingAgent    │ Cal.com meeting booking & founder prep briefing.  │
└────────────────────┴───────────────────────────────────────────────────┘
```

---

## 🔐 Security Setup (do this first)

There are **no default credentials or secrets**. Authentication is mandatory on every `/api/*` route except the health probes.

```bash
python3 scripts/generate_secrets.py     # writes strong JWT / webhook / vault secrets into .env (mode 600)
python3 scripts/create_admin_key.py     # prints your first super_admin API key ONCE
```

| Setting | Purpose |
|---|---|
| `AGENCYBD_ENV` | `development` / `test` / `production`. Production refuses to start with missing, short, placeholder or leaked secrets. |
| `AGENCYBD_JWT_SECRET`, `AGENCYBD_WEBHOOK_SECRET`, `AGENCYBD_HMAC_VAULT_KEY` | Required secrets (≥32 chars). |
| `AGENCYBD_CORS_ORIGINS` | Browser origins allowed to call the API. No wildcard. |
| `AGENCYBD_WEBHOOK_ORG_ID` | Tenant that inbound webhook replies are attributed to. |
| `AGENCYBD_DASHBOARD_PASSWORD` | Streamlit login (required in production). |
| `AGENCYBD_ENABLE_DOCS` | Expose `/docs` in production (off by default). |

- **Callers** send `X-API-Key: <key>` or `Authorization: Bearer <jwt>`. Roles: `super_admin`, `growth_lead`, `sdr_rep`, `auditor`.
- **Tenancy:** the org comes from the credential. Only `super_admin` can pass `?org_id=` for another tenant.
- **Inbound webhooks** must send `X-AgencyBD-Timestamp` and `X-AgencyBD-Signature` = `HMAC_SHA256(secret, "<timestamp>.<raw body>")`; requests older than 5 minutes are rejected.
- **Rotate** with `python3 scripts/generate_secrets.py --rotate` (invalidates existing JWTs).
- The `.env` file is git-ignored and excluded from Docker images. Keep it that way.

---

## 🚀 Quickstart Guide

### 1. Run Automated Test Suite
```bash
python3 -m pytest tests/ -v
```

### 2. Launch FastAPI Microservice Engine
```bash
uvicorn api:app --reload --port 8000
```
Interactive Swagger docs available at: `http://localhost:8000/docs`

### 3. Launch Streamlit Executive Command Center
```bash
streamlit run app.py --server.port 8502
```
Access the control room in your browser at `http://localhost:8502`.
