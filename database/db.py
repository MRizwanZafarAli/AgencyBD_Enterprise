"""
Database Connection & Initialization Layer for AgencyBD_Enterprise.
Uses SQLite with Write-Ahead Logging (WAL), connection timeout pooling,
foreign key cascades, and cryptographic audit logging for unhackable data integrity.
"""

import sqlite3
import threading
import json
from typing import Optional
from contextlib import contextmanager
from pathlib import Path
from config.settings import DB_PATH
from database.security_vault import SecurityVault

def init_db():
    """Initializes tables, indexes, and cryptographic security extensions."""
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA busy_timeout=15000;")
    
    # 1. Leads Table (with Cryptographic HMAC signature)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        domain TEXT NOT NULL UNIQUE,
        phone TEXT,
        address TEXT,
        rating REAL DEFAULT 0.0,
        reviews_count INTEGER DEFAULT 0,
        source_channel TEXT NOT NULL,
        source_query TEXT,
        status TEXT NOT NULL DEFAULT 'sourced',
        notes TEXT,
        record_hash TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 2. Technical Audits Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tech_audits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER NOT NULL,
        load_time_ms INTEGER,
        ttfb_ms INTEGER,
        lcp_score REAL,
        mobile_responsive BOOLEAN,
        tech_stack_json TEXT,
        missing_headers_json TEXT,
        console_errors_json TEXT,
        audit_summary TEXT,
        calculated_pitch_angle TEXT,
        record_hash TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE
    );
    """)

    # 3. Decision Makers Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS decision_makers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        title TEXT NOT NULL,
        linkedin_url TEXT,
        email TEXT NOT NULL UNIQUE,
        email_source TEXT,
        verification_status TEXT DEFAULT 'unverified',
        mx_verified BOOLEAN DEFAULT 0,
        smtp_handshake_status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE
    );
    """)

    # 4. Outreach Sequences Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS outreach_sequences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER NOT NULL,
        decision_maker_id INTEGER,
        step_number INTEGER NOT NULL,
        channel TEXT NOT NULL DEFAULT 'email',
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        spam_score REAL DEFAULT 0.0,
        status TEXT NOT NULL DEFAULT 'drafted',
        sent_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE,
        FOREIGN KEY (decision_maker_id) REFERENCES decision_makers (id)
    );
    """)

    # 5. Inbound Replies Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inbound_replies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER NOT NULL,
        reply_text TEXT NOT NULL,
        sentiment TEXT NOT NULL,
        objection_category TEXT NOT NULL,
        auto_rebuttal_draft TEXT NOT NULL,
        handled BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE
    );
    """)

    # 6. Meeting Bookings Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meeting_bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER NOT NULL,
        decision_maker_id INTEGER,
        booking_time TEXT,
        cal_link TEXT NOT NULL,
        founder_prep_brief TEXT NOT NULL,
        crm_synced BOOLEAN DEFAULT 1,
        record_hash TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE,
        FOREIGN KEY (decision_maker_id) REFERENCES decision_makers (id)
    );
    """)

    # 7. Global Cryptographic Suppression Vault (CAN-SPAM & GDPR)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS suppression_vault (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_hash TEXT NOT NULL UNIQUE,
        entity_type TEXT NOT NULL,
        reason TEXT NOT NULL DEFAULT 'user_unsubscribe',
        source TEXT NOT NULL DEFAULT 'inbound_reply',
        org_id TEXT NOT NULL DEFAULT 'org_default',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppression_hash ON suppression_vault (entity_hash);")

    # 8. Immutable Enterprise Compliance Audit Trail
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_trail (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        metadata_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_lead ON audit_trail (lead_id);")

    # 9. Zero-Trust API Key Vault
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_hash TEXT NOT NULL UNIQUE,
        prefix TEXT NOT NULL,
        name TEXT NOT NULL,
        user_id TEXT NOT NULL,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        role TEXT NOT NULL DEFAULT 'growth_lead',
        revoked BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_key_hash ON api_keys (key_hash);")

    # 10. Financial Ledger & Cost Attribution
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS financial_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        lead_id INTEGER,
        expense_type TEXT NOT NULL,
        amount_usd REAL NOT NULL,
        metadata_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 11. Spintax A/B Cohort Conversion Tracker
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ab_test_cohorts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        variant_key TEXT NOT NULL,
        variant_type TEXT NOT NULL,
        impressions INTEGER DEFAULT 0,
        opens INTEGER DEFAULT 0,
        replies INTEGER DEFAULT 0,
        positive_replies INTEGER DEFAULT 0,
        bounces INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(org_id, variant_key)
    );
    """)

    # 12. Distributed Task Queue & DLQ
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS task_queue (
        id TEXT PRIMARY KEY,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        task_name TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        retries INTEGER DEFAULT 0,
        max_retries INTEGER DEFAULT 3,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_status ON task_queue (status);")

    # ==================== Phase 0/1/2 Enterprise Tables ====================

    # 13. Companies (Canonical Enterprise Company Profile)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        domain TEXT,
        name TEXT NOT NULL,
        place_id TEXT,
        size_band TEXT,
        country TEXT,
        industry TEXT,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(org_id, domain);")

    # 14. People (Decision Makers with Provenance & Legal Basis)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS people (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        company_id INTEGER,
        name TEXT NOT NULL,
        title TEXT,
        email TEXT,
        email_status TEXT DEFAULT 'unverified',
        source TEXT,
        legal_basis TEXT DEFAULT 'legitimate_interest',
        collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_people_email ON people(org_id, email);")

    # 15. Opportunities (Unified Radar Pipeline for All Work)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        type TEXT NOT NULL, -- outbound | marketplace | tender | inbound
        source TEXT NOT NULL, -- upwork | remoteok | wwr | hn | sam_gov | maps
        external_id TEXT,
        company_id INTEGER,
        title TEXT NOT NULL,
        description TEXT,
        budget_min REAL,
        budget_max REAL,
        currency TEXT DEFAULT 'USD',
        posted_at TIMESTAMP,
        deadline TIMESTAMP,
        status TEXT DEFAULT 'discovered', -- discovered | qualified | drafted | approved | submitted | won | lost
        fit_score REAL DEFAULT 0.0,
        risk_flags_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE SET NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_opp_source ON opportunities(org_id, source, status);")

    # 16. Signals (Timing triggers: hiring, funding, tech changes)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        company_id INTEGER NOT NULL,
        type TEXT NOT NULL, -- hiring | funding | tech_change | leadership | review_trend
        payload_json TEXT NOT NULL,
        observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        source TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE
    );
    """)

    # 17. Evidence (Every claim backed by stored, timestamped proof)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS evidence (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        entity_type TEXT NOT NULL, -- company | website | audit | market
        entity_id INTEGER NOT NULL,
        claim TEXT NOT NULL,
        value TEXT NOT NULL,
        source_url TEXT,
        method TEXT NOT NULL, -- lighthouse | headers | ssl | crawler | api
        observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        confidence REAL DEFAULT 1.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_entity ON evidence(entity_type, entity_id);")

    # 18. Audit Runs & Findings (Website Doctor Results)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        company_id INTEGER,
        domain TEXT NOT NULL,
        overall_score INTEGER DEFAULT 0,
        status TEXT DEFAULT 'completed',
        summary TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        audit_run_id INTEGER NOT NULL,
        category TEXT NOT NULL, -- performance | seo | security | a11y | ux | geo | dns
        check_id TEXT NOT NULL,
        severity TEXT NOT NULL, -- critical | high | medium | low | info
        finding TEXT NOT NULL,
        fix TEXT,
        estimated_impact TEXT,
        service_id TEXT,
        evidence_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (audit_run_id) REFERENCES audit_runs (id) ON DELETE CASCADE
    );
    """)

    # 19. Service Playbooks
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        name TEXT NOT NULL,
        signals_json TEXT,
        offer TEXT NOT NULL,
        price_band TEXT,
        objections_json TEXT,
        proof_assets_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 20. Portfolio Assets (Agency Case Studies & RAG Vault)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS portfolio_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        title TEXT NOT NULL,
        industry TEXT,
        services_json TEXT,
        tech_json TEXT,
        metrics_json TEXT,
        body TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 21. Proposals & Human Approval Gate
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS proposals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        opportunity_id INTEGER NOT NULL,
        variant TEXT DEFAULT 'A',
        body TEXT NOT NULL,
        status TEXT DEFAULT 'draft', -- draft | approved | submitted | won | lost
        model TEXT,
        prompt_version TEXT,
        outcome_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (opportunity_id) REFERENCES opportunities (id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS approvals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        subject_type TEXT NOT NULL, -- proposal | outbound_batch | contract
        subject_id INTEGER NOT NULL,
        requested_by TEXT NOT NULL,
        decided_by TEXT,
        decision TEXT DEFAULT 'pending', -- pending | approved | rejected | edited
        reason TEXT,
        decided_at TIMESTAMP
    );
    """)

    # 22. Policy Engine & Autonomy Decisions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS policies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        rule_name TEXT NOT NULL,
        level TEXT NOT NULL DEFAULT 'L1', -- L0 | L1 | L2 | L3 | NEVER
        config_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(org_id, rule_name)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS policy_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        rule_name TEXT NOT NULL,
        input_json TEXT,
        allowed BOOLEAN NOT NULL,
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 23. Agent Runs (Observability, Tokens, Cost, Traces)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        agent_name TEXT NOT NULL,
        model TEXT NOT NULL,
        prompt_version TEXT DEFAULT 'v1',
        tokens_in INTEGER DEFAULT 0,
        tokens_out INTEGER DEFAULT 0,
        cost_usd REAL DEFAULT 0.0,
        latency_ms INTEGER DEFAULT 0,
        input_ref TEXT,
        output_ref TEXT,
        status TEXT DEFAULT 'success',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 24. Mailboxes (Outbound Sender Inboxes with Daily Caps & Health)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mailboxes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        email TEXT NOT NULL,
        display_name TEXT,
        provider_type TEXT NOT NULL DEFAULT 'smtp', -- smtp | google | microsoft | smartlead
        daily_cap INTEGER DEFAULT 35,
        sent_today INTEGER DEFAULT 0,
        reputation_status TEXT DEFAULT 'healthy', -- healthy | warning | paused
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(org_id, email)
    );
    """)

    # 25. Outreach Events (Sent, Delivered, Opened, Replied, Bounced, Unsubscribed)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS outreach_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL DEFAULT 'org_default',
        mailbox_id INTEGER,
        lead_id INTEGER,
        recipient_email TEXT NOT NULL,
        event_type TEXT NOT NULL, -- sent | delivered | opened | replied | bounced | complaint | unsubscribed
        message_id TEXT,
        payload_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_outreach_events_email ON outreach_events(org_id, recipient_email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_outreach_events_type ON outreach_events(org_id, event_type);")


    # Composite Unique Index Migrations (Multi-Tenant Isolation)
    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_org_domain ON leads(org_id, domain);")
    except Exception:
        pass

    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_dm_org_email ON decision_makers(org_id, email);")
    except Exception:
        pass

    # Safe Schema Migrations: Ensure record_hash and org_id exist across tables
    for tbl in ["leads", "tech_audits", "meeting_bookings"]:
        try:
            cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN record_hash TEXT;")
        except Exception:
            pass

    for tbl in ["leads", "tech_audits", "decision_makers", "outreach_sequences", "inbound_replies", "meeting_bookings", "suppression_vault", "audit_trail"]:
        try:
            cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN org_id TEXT DEFAULT 'org_default';")
        except Exception:
            pass

    # Proposal grounding columns (added after first release) and opportunity de-duplication
    for stmt in (
        "ALTER TABLE proposals ADD COLUMN verification_json TEXT;",
        "ALTER TABLE proposals ADD COLUMN cited_assets_json TEXT;",
        "ALTER TABLE portfolio_assets ADD COLUMN source_url TEXT;",
    ):
        try:
            cursor.execute(stmt)
        except Exception:
            pass
    for stmt in (
        "ALTER TABLE services ADD COLUMN service_key TEXT;",
        "ALTER TABLE opportunities ADD COLUMN url TEXT;",
        "ALTER TABLE opportunities ADD COLUMN company_name TEXT;",
        "ALTER TABLE opportunities ADD COLUMN skills_json TEXT;",
        "ALTER TABLE opportunities ADD COLUMN fit_reasons_json TEXT;",
        "ALTER TABLE mailboxes ADD COLUMN esp TEXT;",
        "ALTER TABLE mailboxes ADD COLUMN skip_warmup INTEGER DEFAULT 0;",
    ):
        try:
            cursor.execute(stmt)
        except Exception:
            pass
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS mailbox_credentials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL,
        mailbox_id INTEGER NOT NULL UNIQUE,
        smtp_host TEXT NOT NULL,
        smtp_port INTEGER NOT NULL DEFAULT 587,
        smtp_username TEXT NOT NULL,
        password_enc TEXT NOT NULL,
        use_tls INTEGER NOT NULL DEFAULT 1,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (mailbox_id) REFERENCES mailboxes (id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS email_verifications (
        email_hash TEXT PRIMARY KEY,
        status TEXT NOT NULL,            -- verified | invalid | risky | unknown
        provider TEXT NOT NULL,
        detail TEXT,
        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS outbound_drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL,
        lead_id INTEGER,
        enrollment_id INTEGER,
        recipient_email TEXT NOT NULL,
        recipient_name TEXT,
        company_name TEXT,
        country_code TEXT NOT NULL,
        step_number INTEGER NOT NULL DEFAULT 1,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        deal_value REAL,
        status TEXT NOT NULL DEFAULT 'pending_approval', -- pending_approval | approved | rejected | sent | failed
        policy_rule TEXT,
        send_result_json TEXT,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        decided_at TIMESTAMP,
        sent_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS sequences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL,
        name TEXT NOT NULL,
        steps_json TEXT NOT NULL,        -- [{step_number, delay_days, subject, body}]
        status TEXT NOT NULL DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS sequence_enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL,
        sequence_id INTEGER NOT NULL,
        lead_id INTEGER,
        recipient_email TEXT NOT NULL,
        recipient_name TEXT,
        company_name TEXT,
        country_code TEXT NOT NULL,
        deal_value REAL,
        current_step INTEGER NOT NULL DEFAULT 1,
        next_run_at TIMESTAMP NOT NULL,
        status TEXT NOT NULL DEFAULT 'active', -- active | awaiting_approval | completed | stopped
        stop_reason TEXT,
        attempts INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sequence_id) REFERENCES sequences (id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_enroll_due ON sequence_enrollments(status, next_run_at);
    CREATE TABLE IF NOT EXISTS connector_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL,
        source TEXT NOT NULL,
        status TEXT NOT NULL,            -- ok | empty | error | not_configured | not_connected
        fetched INTEGER NOT NULL DEFAULT 0,
        stored INTEGER NOT NULL DEFAULT 0,
        detail TEXT,
        ran_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_connector_runs ON connector_runs(org_id, source, id);
    CREATE TABLE IF NOT EXISTS oauth_tokens (
        org_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        access_enc TEXT NOT NULL,
        refresh_enc TEXT,
        expires_at TIMESTAMP,
        scope TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (org_id, provider)
    );
    CREATE TABLE IF NOT EXISTS webhook_secrets (
        org_id TEXT PRIMARY KEY,
        secret_enc TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS work_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL,
        kind TEXT NOT NULL,              -- find_contact | review_lead | fix_setup | new_cve | reply | custom
        title TEXT NOT NULL,
        detail TEXT,
        entity_type TEXT,
        entity_id INTEGER,
        priority INTEGER NOT NULL DEFAULT 50,
        status TEXT NOT NULL DEFAULT 'open',   -- open | done | dismissed
        dedupe_key TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_work_items_open ON work_items(org_id, status, priority DESC);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_work_items_dedupe ON work_items(org_id, dedupe_key) WHERE dedupe_key IS NOT NULL AND status = 'open';
    CREATE TABLE IF NOT EXISTS lead_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL,
        lead_id INTEGER NOT NULL,
        score INTEGER NOT NULL,
        band TEXT NOT NULL,
        components_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_lead_scores_lead ON lead_scores(org_id, lead_id, id DESC);
    CREATE TABLE IF NOT EXISTS org_controls (
        org_id TEXT PRIMARY KEY,
        outbound_halted INTEGER NOT NULL DEFAULT 0,
        reason TEXT,
        changed_by TEXT,
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS agency_profile (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,             -- '' is an explicit clear that overrides .env; deleting the row restores .env
        set_by TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS integration_keys (
        name TEXT PRIMARY KEY,
        value_enc TEXT NOT NULL,
        set_by TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS channel_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL,
        platform TEXT NOT NULL,
        type TEXT NOT NULL,              -- link | pipeline | template | routine | done | activity | message | setting
        data_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_channel_records ON channel_records(org_id, platform, type);
    CREATE TABLE IF NOT EXISTS client_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL,
        lead_id INTEGER NOT NULL,
        kind TEXT NOT NULL,              -- note | task
        body TEXT NOT NULL,
        due_date TEXT,                   -- YYYY-MM-DD, tasks only
        done_at TIMESTAMP,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_client_notes ON client_notes(org_id, lead_id);
    CREATE TABLE IF NOT EXISTS vuln_cache (
        cache_key TEXT PRIMARY KEY,
        payload_json TEXT NOT NULL,
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS discovery_runs (
        id TEXT PRIMARY KEY,
        org_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'running',   -- running | done | failed
        params_json TEXT,
        progress_json TEXT,
        result_json TEXT,
        error TEXT,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        finished_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS job_runs (
        job TEXT NOT NULL,
        org_id TEXT NOT NULL DEFAULT '*',
        last_run_at TIMESTAMP,
        detail TEXT,
        PRIMARY KEY (job, org_id)
    );
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_opp_org_source_ext
        ON opportunities(org_id, source, external_id) WHERE external_id IS NOT NULL;
    """)

    conn.commit()
    conn.close()

_thread_state = threading.local()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 15000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_db():
    """
    Context manager yielding this thread's SQLite connection (created once, reused). Opening and closing a connection per call made
    concurrent writers crawl in WAL mode (shared-memory setup and a checkpoint on every last close). Semantics are unchanged: a
    transaction that was not committed is rolled back when the block ends, exactly as closing the connection used to do.
    """
    path = str(DB_PATH)
    pool = getattr(_thread_state, "pool", None)
    if pool is None:
        pool = _thread_state.pool = {}
    conn = pool.get(path)
    if conn is None:
        conn = pool[path] = _connect()
    depth = getattr(_thread_state, "depth", 0)
    _thread_state.depth = depth + 1
    try:
        yield conn
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        _thread_state.depth = depth
        if depth == 0 and conn.in_transaction:        # outermost block: discard anything that was not committed
            conn.rollback()


def log_audit_trail(lead_id: Optional[int], actor: str, action: str, metadata: dict, conn: Optional[sqlite3.Connection] = None) -> None:
    """Appends an immutable audit event for security and compliance monitoring."""
    if conn is not None:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_trail (lead_id, actor, action, metadata_json, org_id)
            VALUES (?, ?, ?, ?, COALESCE((SELECT org_id FROM leads WHERE id = ?), 'org_default'))
        """, (lead_id, actor, action, json.dumps(metadata, default=str), lead_id))
        return

    with get_db() as c:
        cursor = c.cursor()
        cursor.execute("""
            INSERT INTO audit_trail (lead_id, actor, action, metadata_json, org_id)
            VALUES (?, ?, ?, ?, COALESCE((SELECT org_id FROM leads WHERE id = ?), 'org_default'))
        """, (lead_id, actor, action, json.dumps(metadata, default=str), lead_id))
        c.commit()

def is_entity_suppressed(email_or_domain: str, conn: Optional[sqlite3.Connection] = None) -> bool:
    """Checks constant-time SHA-256 hash against global suppression vault."""
    clean_val = email_or_domain.lower().strip()
    target_hash = SecurityVault.generate_sha256_hash(clean_val)
    if conn is not None:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM suppression_vault WHERE entity_hash = ?", (target_hash,))
        return cursor.fetchone() is not None

    with get_db() as c:
        cursor = c.cursor()
        cursor.execute("SELECT 1 FROM suppression_vault WHERE entity_hash = ?", (target_hash,))
        return cursor.fetchone() is not None

def add_entity_to_suppression(email_or_domain: str, entity_type: str = "email", reason: str = "user_unsubscribe", conn: Optional[sqlite3.Connection] = None) -> None:
    """Permanently hashes and suppresses an entity from all future campaigns."""
    clean_val = email_or_domain.lower().strip()
    target_hash = SecurityVault.generate_sha256_hash(clean_val)
    if conn is not None:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO suppression_vault (entity_hash, entity_type, reason)
            VALUES (?, ?, ?)
        """, (target_hash, entity_type, reason))
        return

    with get_db() as c:
        cursor = c.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO suppression_vault (entity_hash, entity_type, reason)
            VALUES (?, ?, ?)
        """, (target_hash, entity_type, reason))
        c.commit()

def create_api_key_record(name: str, user_id: str, role: str = "growth_lead", org_id: str = "org_default") -> str:
    """Generates an API key, stores its SHA-256 hash in database, and returns the plaintext key once."""
    from security.auth import SecurityService, ROLE_PERMISSIONS
    if role not in ROLE_PERMISSIONS:
        raise ValueError(f"Unknown role '{role}'. Valid roles: {sorted(ROLE_PERMISSIONS)}")
    raw_key = SecurityService.generate_api_key()
    key_hash = SecurityService.hash_api_key(raw_key)
    prefix = raw_key[:12] + "..."

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO api_keys (key_hash, prefix, name, user_id, org_id, role, revoked)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (key_hash, prefix, name, user_id, org_id, role))
        conn.commit()
    return raw_key

def list_api_keys(org_id: str = "org_default") -> list:
    """Lists non-sensitive metadata for registered API keys."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, prefix, name, user_id, org_id, role, revoked, created_at
            FROM api_keys
            WHERE org_id = ?
            ORDER BY id DESC
        """, (org_id,))
        return [dict(r) for r in cursor.fetchall()]

def revoke_api_key_record(key_id: int, org_id: str = "org_default") -> bool:
    """Revokes an API key instantly."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE api_keys SET revoked = 1 WHERE id = ? AND org_id = ?", (key_id, org_id))
        conn.commit()
        return cursor.rowcount > 0

