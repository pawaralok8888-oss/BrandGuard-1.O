-- BrandGuard schema.sql | PostgreSQL 16 + pgvector
-- Idempotent schema for the fictional GreenGlow demo.
CREATE EXTENSION IF NOT EXISTS vector;
BEGIN;

CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE,
 role TEXT NOT NULL CHECK (role IN ('creator','manager','reviewer','admin')),
 initials TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '', avatar_color TEXT NOT NULL DEFAULT '#315B45',
 team TEXT NOT NULL CHECK (team IN ('Marketing','Sales','Brand','Legal','Product','Design','HR','Support')),
 is_demo_login BOOLEAN NOT NULL DEFAULT FALSE, persona_description TEXT NOT NULL DEFAULT '',
 demo_route TEXT NOT NULL DEFAULT '/content', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS teams (
 name TEXT PRIMARY KEY CHECK (name IN ('Marketing','Sales','Brand','Legal','Product','Design','HR','Support')), description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS products (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, approved_name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'skincare', is_released BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS facts (
 id TEXT PRIMARY KEY, product_id TEXT REFERENCES products(id) ON DELETE SET NULL, title TEXT NOT NULL, statement TEXT NOT NULL,
 fact_type TEXT NOT NULL CHECK (fact_type IN ('name','price','claim','certification','offer','spec','ingredient','policy')),
 structured_value JSONB NOT NULL DEFAULT '{}'::jsonb, match_keywords TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[], match_regex TEXT,
 severity_on_change TEXT NOT NULL DEFAULT 'Medium' CHECK (severity_on_change IN ('High','Medium')),
 owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT, version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
 valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_until DATE,
 status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active','Expiring soon','Expired')),
 category TEXT NOT NULL DEFAULT 'Brand', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS fact_versions (
 fact_id TEXT NOT NULL REFERENCES facts(id) ON DELETE CASCADE, version INTEGER NOT NULL CHECK (version > 0), statement TEXT NOT NULL,
 structured_value JSONB NOT NULL DEFAULT '{}'::jsonb, note TEXT NOT NULL DEFAULT '', owner TEXT NOT NULL DEFAULT '',
 changed_by TEXT REFERENCES users(id) ON DELETE SET NULL, changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_until DATE, PRIMARY KEY (fact_id,version)
);
CREATE TABLE IF NOT EXISTS guidelines (
 id TEXT PRIMARY KEY, short_name TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL,
 category TEXT NOT NULL CHECK (category IN ('Terminology','Claims & Legal','Tone of Voice','Formatting','Accessibility','Brand Assets','Security')),
 rule_type TEXT NOT NULL DEFAULT 'warning', severity TEXT NOT NULL DEFAULT 'warning' CHECK (severity IN ('critical','warning','info')),
 applies_to_channels TEXT[] NOT NULL DEFAULT ARRAY['Website','Instagram','Email','Ad']::TEXT[], required_text TEXT,
 version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0), owner_id TEXT REFERENCES users(id) ON DELETE SET NULL,
 is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS guideline_versions (
 guideline_id TEXT NOT NULL REFERENCES guidelines(id) ON DELETE CASCADE, version INTEGER NOT NULL CHECK (version > 0), text TEXT NOT NULL,
 changed_by TEXT REFERENCES users(id) ON DELETE SET NULL, change_note TEXT NOT NULL DEFAULT '', changed_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (guideline_id,version)
);
CREATE TABLE IF NOT EXISTS glossary (
 id TEXT PRIMARY KEY, approved_term TEXT NOT NULL, avoid_terms TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
 kind TEXT NOT NULL CHECK (kind IN ('term','product_name')), explanation TEXT NOT NULL DEFAULT '', is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS assets (
 id TEXT PRIMARY KEY, label TEXT NOT NULL, asset_type TEXT NOT NULL CHECK (asset_type IN ('logo','colour','font','image','template','other')),
 version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0), status TEXT NOT NULL DEFAULT 'approved' CHECK (status IN ('approved','deprecated','draft')),
 file_path TEXT, hex TEXT, phash TEXT, aspect_ratio NUMERIC(10,5), width INTEGER, height INTEGER, usage_note TEXT NOT NULL DEFAULT '',
 metadata JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS content (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, channel TEXT NOT NULL CHECK (channel IN ('Website','Instagram','Email','Ad')),
 asset_type TEXT NOT NULL DEFAULT 'social_post',
 format TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT 'skincare', description TEXT NOT NULL DEFAULT '',
 team TEXT NOT NULL CHECK (team IN ('Marketing','Sales','Brand','Legal','Product','Design','HR','Support')),
 owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT, assigned_reviewer_id TEXT REFERENCES users(id) ON DELETE SET NULL,
 status TEXT NOT NULL CHECK (status IN ('Draft','Checked','Fixing','In Review','Changes requested','Approved','Published','Needs revalidation')),
 body_text TEXT NOT NULL DEFAULT '', body_html TEXT NOT NULL DEFAULT '',
 thumbnail_art TEXT CHECK (thumbnail_art IS NULL OR thumbnail_art IN ('sunscreen','facewash','serum','email','routine','offer')),
 image_url TEXT, alt_text TEXT, image_width INTEGER, image_height INTEGER, submitted_at TIMESTAMPTZ, approved_at TIMESTAMPTZ, published_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CHECK (image_width IS NULL OR image_width > 0), CHECK (image_height IS NULL OR image_height > 0)
);
ALTER TABLE content ADD COLUMN IF NOT EXISTS asset_type TEXT NOT NULL DEFAULT 'social_post';
CREATE TABLE IF NOT EXISTS content_versions (
 id TEXT PRIMARY KEY, content_id TEXT NOT NULL REFERENCES content(id) ON DELETE CASCADE, version INTEGER NOT NULL CHECK (version > 0),
 body_text TEXT NOT NULL, body_html TEXT NOT NULL DEFAULT '', change_type TEXT NOT NULL CHECK (change_type IN ('initial','ai_fix','human_edit','reviewer_edit','restore','other')),
 actor_id TEXT REFERENCES users(id) ON DELETE SET NULL, actor_label TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(content_id,version)
);
CREATE TABLE IF NOT EXISTS check_runs (
 id TEXT PRIMARY KEY, content_id TEXT NOT NULL REFERENCES content(id) ON DELETE CASCADE, started_at TIMESTAMPTZ NOT NULL DEFAULT now(), finished_at TIMESTAMPTZ,
 rules_count INTEGER NOT NULL DEFAULT 0 CHECK (rules_count >= 0), ai_count INTEGER NOT NULL DEFAULT 0 CHECK (ai_count >= 0),
 rules_only_fallback BOOLEAN NOT NULL DEFAULT FALSE, metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS findings (
 id TEXT PRIMARY KEY, content_id TEXT NOT NULL REFERENCES content(id) ON DELETE CASCADE, check_run_id TEXT REFERENCES check_runs(id) ON DELETE SET NULL,
 type TEXT NOT NULL CHECK (type IN ('rule','claim','tone','image','accessibility','security')), start INTEGER, "end" INTEGER, bbox NUMERIC[],
 severity TEXT NOT NULL CHECK (severity IN ('critical','warning','info')), title TEXT NOT NULL, reason TEXT NOT NULL,
 source_id TEXT NOT NULL, source_version INTEGER NOT NULL CHECK (source_version > 0), guideline_id TEXT REFERENCES guidelines(id) ON DELETE SET NULL,
 suggested_fix TEXT NOT NULL DEFAULT '', original_text TEXT, confidence NUMERIC(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
 ai_generated BOOLEAN NOT NULL DEFAULT FALSE, needs_human_review BOOLEAN NOT NULL DEFAULT FALSE,
 status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','accepted','edited','rejected','resolved')),
 suggestion_kind TEXT NOT NULL CHECK (suggestion_kind IN ('Tone rewrite','Claim correction','Suggested disclaimer','Terminology change','Visual suggestion')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), CHECK ((start IS NULL AND "end" IS NULL) OR (start >= 0 AND "end" >= start)), CHECK (bbox IS NULL OR cardinality(bbox)=4)
);
CREATE TABLE IF NOT EXISTS decisions (
 id TEXT PRIMARY KEY, finding_id TEXT NOT NULL REFERENCES findings(id) ON DELETE CASCADE, content_id TEXT NOT NULL REFERENCES content(id) ON DELETE CASCADE,
 actor_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT, action TEXT NOT NULL CHECK (action IN ('accept','edit','reject')),
 note TEXT NOT NULL DEFAULT '', reject_reason TEXT, edited_text TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS revisions (
 id TEXT PRIMARY KEY, content_id TEXT NOT NULL REFERENCES content(id) ON DELETE CASCADE, actor_id TEXT REFERENCES users(id) ON DELETE SET NULL,
 actor_label TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL CHECK (kind IN ('person','ai')), action TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
 from_status TEXT, to_status TEXT, version INTEGER, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS comments (
 id TEXT PRIMARY KEY, content_id TEXT NOT NULL REFERENCES content(id) ON DELETE CASCADE, author_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 finding_id TEXT REFERENCES findings(id) ON DELETE SET NULL, body TEXT NOT NULL,
 comment_type TEXT NOT NULL DEFAULT 'review' CHECK (comment_type IN ('review','decision','general','system')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS fact_content_links (
 id TEXT PRIMARY KEY, content_id TEXT NOT NULL REFERENCES content(id) ON DELETE CASCADE,
 source_kind TEXT NOT NULL CHECK (source_kind IN ('fact','guideline','asset')), fact_id TEXT REFERENCES facts(id) ON DELETE CASCADE,
 guideline_id TEXT REFERENCES guidelines(id) ON DELETE CASCADE, asset_id TEXT REFERENCES assets(id) ON DELETE CASCADE,
 source_id TEXT NOT NULL, source_version INTEGER NOT NULL CHECK (source_version > 0), match_reason TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CHECK ((source_kind='fact' AND fact_id IS NOT NULL AND guideline_id IS NULL AND asset_id IS NULL) OR
        (source_kind='guideline' AND fact_id IS NULL AND guideline_id IS NOT NULL AND asset_id IS NULL) OR
        (source_kind='asset' AND fact_id IS NULL AND guideline_id IS NULL AND asset_id IS NOT NULL)),
 UNIQUE(content_id,source_kind,source_id,source_version)
);
CREATE TABLE IF NOT EXISTS alerts (
 id TEXT PRIMARY KEY, recipient_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, content_id TEXT REFERENCES content(id) ON DELETE CASCADE,
 source_id TEXT NOT NULL, source_version INTEGER NOT NULL CHECK (source_version > 0), priority TEXT NOT NULL CHECK (priority IN ('High','Medium')),
 status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','updated','dismissed')), title TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
 old_value TEXT, new_value TEXT, old_text TEXT, suggested_fix TEXT, reminder_count INTEGER NOT NULL DEFAULT 0 CHECK (reminder_count >= 0),
 last_reminder_at TIMESTAMPTZ, read_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ai_calls (
 id TEXT PRIMARY KEY, content_id TEXT REFERENCES content(id) ON DELETE SET NULL, check_run_id TEXT REFERENCES check_runs(id) ON DELETE SET NULL,
 provider TEXT NOT NULL DEFAULT 'anthropic', model TEXT NOT NULL DEFAULT '', purpose TEXT NOT NULL DEFAULT 'claim_tone_check', input_hash TEXT,
 status TEXT NOT NULL DEFAULT 'success' CHECK (status IN ('success','failed','cached','fallback')), latency_ms INTEGER, input_tokens INTEGER, output_tokens INTEGER,
 error_message TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS rule_patterns (
 id TEXT PRIMARY KEY, guideline_id TEXT REFERENCES guidelines(id) ON DELETE SET NULL,
 kind TEXT NOT NULL CHECK (kind IN ('phrase','regex','name_variant','confidential_term','required_text')),
 pattern TEXT NOT NULL, replacement TEXT NOT NULL DEFAULT '', case_sensitive BOOLEAN NOT NULL DEFAULT FALSE, note TEXT NOT NULL DEFAULT '',
 channel TEXT CHECK (channel IS NULL OR channel IN ('Website','Instagram','Email','Ad')), is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sample_drafts (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, channel TEXT NOT NULL CHECK (channel IN ('Website','Instagram','Email','Ad')),
 body_text TEXT NOT NULL, image_url TEXT, alt_text TEXT, blurb TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS quality_metrics (
 id TEXT PRIMARY KEY, rule_key TEXT NOT NULL, precision NUMERIC(4,3) NOT NULL CHECK (precision BETWEEN 0 AND 1),
 recall NUMERIC(4,3) NOT NULL CHECK (recall BETWEEN 0 AND 1), n INTEGER NOT NULL CHECK (n >= 0), run_at TIMESTAMPTZ NOT NULL DEFAULT now(), metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS notification_log (
 id TEXT PRIMARY KEY, channel TEXT NOT NULL CHECK (channel IN ('slack','email','inapp')), recipient_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 subject TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'sent' CHECK (status IN ('queued','sent','failed','read')), created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ai_cache (
 input_hash TEXT PRIMARY KEY, output_json JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Embeddings intentionally survive demo resets; reset_demo must not truncate this table.
CREATE TABLE IF NOT EXISTS embeddings (
 id BIGSERIAL PRIMARY KEY, kind TEXT NOT NULL CHECK (kind IN ('fact','guideline','asset')), source_id TEXT NOT NULL,
 version INTEGER NOT NULL CHECK (version > 0), vector vector(1024), created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(kind,source_id,version)
);

-- Phase 1 intake and uploaded-guideline test data; mirrored in the additive migration.
CREATE TABLE IF NOT EXISTS intake_specs (
    spec_key TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    source_file TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status_values JSONB NOT NULL CHECK (jsonb_typeof(status_values) = 'array'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (spec_key, version)
);
CREATE TABLE IF NOT EXISTS intake_categories (
    spec_key TEXT NOT NULL,
    spec_version INTEGER NOT NULL,
    category_key TEXT NOT NULL,
    label TEXT NOT NULL,
    asset_types JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(asset_types) = 'array'),
    checker_types JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(checker_types) = 'array'),
    sort_order INTEGER NOT NULL CHECK (sort_order > 0),
    PRIMARY KEY (spec_key, spec_version, category_key),
    FOREIGN KEY (spec_key, spec_version)
        REFERENCES intake_specs(spec_key, version) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS intake_fields (
    spec_key TEXT NOT NULL,
    spec_version INTEGER NOT NULL,
    category_key TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT NOT NULL CHECK (field_type IN ('list', 'table', 'text', 'file')),
    required BOOLEAN NOT NULL,
    check_type TEXT NOT NULL,
    column_names JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(column_names) = 'array'),
    sort_order INTEGER NOT NULL CHECK (sort_order > 0),
    PRIMARY KEY (spec_key, spec_version, category_key, field_key),
    FOREIGN KEY (spec_key, spec_version, category_key)
        REFERENCES intake_categories(spec_key, spec_version, category_key) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS guideline_categories (
    category_key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    applies_to JSONB NOT NULL CHECK (jsonb_typeof(applies_to) = 'array'),
    checker TEXT NOT NULL,
    source_file TEXT NOT NULL,
    sort_order INTEGER NOT NULL CHECK (sort_order > 0),
    asset_types JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(asset_types) = 'array'),
    checker_types JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(checker_types) = 'array')
);
ALTER TABLE guideline_categories
    ADD COLUMN IF NOT EXISTS asset_types JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(asset_types) = 'array');
ALTER TABLE guideline_categories
    ADD COLUMN IF NOT EXISTS checker_types JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(checker_types) = 'array');
CREATE TABLE IF NOT EXISTS reference_documents (
    document_key TEXT PRIMARY KEY,
    brand_name TEXT NOT NULL,
    document_type TEXT NOT NULL CHECK (document_type IN ('brand_guideline', 'claims_test', 'spec_test')),
    source_file TEXT NOT NULL UNIQUE,
    source_format TEXT NOT NULL CHECK (source_format IN ('markdown', 'pdf', 'docx')),
    is_mock BOOLEAN NOT NULL DEFAULT TRUE,
    content_text TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object')
);
CREATE TABLE IF NOT EXISTS guideline_test_cases (
    case_id TEXT PRIMARY KEY,
    brand_name TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('Website', 'Instagram', 'Email', 'Ad')),
    source_guideline_file TEXT NOT NULL,
    source_document_available BOOLEAN NOT NULL,
    source_test_file TEXT NOT NULL,
    body_text TEXT NOT NULL,
    expected_findings JSONB NOT NULL CHECK (jsonb_typeof(expected_findings) = 'array'),
    sort_order INTEGER NOT NULL CHECK (sort_order > 0)
);
CREATE INDEX IF NOT EXISTS idx_intake_fields_order
    ON intake_fields(spec_key, spec_version, category_key, sort_order);
CREATE INDEX IF NOT EXISTS idx_guideline_test_cases_brand_channel
    ON guideline_test_cases(brand_name, channel, sort_order);

-- Required FK and query indexes.
CREATE INDEX IF NOT EXISTS idx_facts_product_id ON facts(product_id);
CREATE INDEX IF NOT EXISTS idx_facts_owner_id ON facts(owner_id);
CREATE INDEX IF NOT EXISTS idx_fact_versions_changed_by ON fact_versions(changed_by);
CREATE INDEX IF NOT EXISTS idx_guidelines_owner_id ON guidelines(owner_id);
CREATE INDEX IF NOT EXISTS idx_guideline_versions_changed_by ON guideline_versions(changed_by);
CREATE INDEX IF NOT EXISTS idx_content_owner_id ON content(owner_id);
CREATE INDEX IF NOT EXISTS idx_content_assigned_reviewer_id ON content(assigned_reviewer_id);
CREATE INDEX IF NOT EXISTS idx_content_status ON content(status);
CREATE INDEX IF NOT EXISTS idx_content_versions_content_id ON content_versions(content_id);
CREATE INDEX IF NOT EXISTS idx_content_versions_actor_id ON content_versions(actor_id);
CREATE INDEX IF NOT EXISTS idx_check_runs_content_id ON check_runs(content_id);
CREATE INDEX IF NOT EXISTS idx_findings_content_id ON findings(content_id);
CREATE INDEX IF NOT EXISTS idx_findings_check_run_id ON findings(check_run_id);
CREATE INDEX IF NOT EXISTS idx_findings_guideline_id ON findings(guideline_id);
CREATE INDEX IF NOT EXISTS idx_findings_source_id ON findings(source_id);
CREATE INDEX IF NOT EXISTS idx_decisions_finding_id ON decisions(finding_id);
CREATE INDEX IF NOT EXISTS idx_decisions_content_id ON decisions(content_id);
CREATE INDEX IF NOT EXISTS idx_decisions_actor_id ON decisions(actor_id);
CREATE INDEX IF NOT EXISTS idx_revisions_content_id ON revisions(content_id);
CREATE INDEX IF NOT EXISTS idx_revisions_actor_id ON revisions(actor_id);
CREATE INDEX IF NOT EXISTS idx_comments_content_id ON comments(content_id);
CREATE INDEX IF NOT EXISTS idx_comments_author_id ON comments(author_id);
CREATE INDEX IF NOT EXISTS idx_comments_finding_id ON comments(finding_id);
CREATE INDEX IF NOT EXISTS idx_fact_content_links_content_id ON fact_content_links(content_id);
CREATE INDEX IF NOT EXISTS idx_fact_content_links_fact_id ON fact_content_links(fact_id);
CREATE INDEX IF NOT EXISTS idx_fact_content_links_guideline_id ON fact_content_links(guideline_id);
CREATE INDEX IF NOT EXISTS idx_fact_content_links_asset_id ON fact_content_links(asset_id);
CREATE INDEX IF NOT EXISTS idx_fact_content_links_source_id ON fact_content_links(source_id);
CREATE INDEX IF NOT EXISTS idx_alerts_recipient_status ON alerts(recipient_id,status);
CREATE INDEX IF NOT EXISTS idx_alerts_content_id ON alerts(content_id);
CREATE INDEX IF NOT EXISTS idx_alerts_source_id ON alerts(source_id);
CREATE INDEX IF NOT EXISTS idx_ai_calls_content_id ON ai_calls(content_id);
CREATE INDEX IF NOT EXISTS idx_ai_calls_check_run_id ON ai_calls(check_run_id);
CREATE INDEX IF NOT EXISTS idx_rule_patterns_guideline_id ON rule_patterns(guideline_id);
CREATE INDEX IF NOT EXISTS idx_notification_log_recipient_id ON notification_log(recipient_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_source ON embeddings(kind,source_id,version);
CREATE INDEX IF NOT EXISTS idx_findings_created_at ON findings(created_at);
CREATE INDEX IF NOT EXISTS idx_revisions_created_at ON revisions(created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_content_channel ON content(channel);
CREATE INDEX IF NOT EXISTS idx_content_team ON content(team);
CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_facts_status ON facts(status);
CREATE INDEX IF NOT EXISTS idx_guidelines_category ON guidelines(category);
CREATE INDEX IF NOT EXISTS idx_rule_patterns_active_kind ON rule_patterns(is_active,kind);
CREATE INDEX IF NOT EXISTS idx_fact_content_links_content_source ON fact_content_links(content_id,source_kind,source_id);

INSERT INTO teams(name,description) VALUES
 ('Marketing','Campaigns and social content'),('Sales','Sales enablement and offers'),
 ('Brand','Brand governance and administration'),('Legal','Claims, compliance and review'),
 ('Product','Product facts and product communications'),('Design','Creative assets and visual design'),
 ('HR','Internal people communications; exclude from marketing fact alerts'),
 ('Support','Customer support communications; exclude from marketing fact alerts')
ON CONFLICT(name) DO NOTHING;
COMMIT;
