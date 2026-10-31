-- Brand rules with a draft -> approved -> retired lifecycle, and the history of each change.
-- Idempotent: safe to run on a database that already has these tables.
CREATE TABLE IF NOT EXISTS brand_rules (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('phrase','regex','name_variant','required_text')),
  pattern TEXT NOT NULL,
  replacement TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL DEFAULT '',
  channel TEXT CHECK (channel IS NULL OR channel IN ('Website','Instagram','Email','Ad')),
  severity TEXT NOT NULL DEFAULT 'warning' CHECK (severity IN ('critical','warning','info')),
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','retired')),
  created_by TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  approved_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  approved_at TIMESTAMPTZ,
  retired_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status <> 'approved' OR approved_by IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_brand_rules_status ON brand_rules(status);

CREATE TABLE IF NOT EXISTS brand_rule_history (
  id BIGSERIAL PRIMARY KEY,
  brand_rule_id TEXT NOT NULL REFERENCES brand_rules(id) ON DELETE CASCADE,
  from_status TEXT,
  to_status TEXT NOT NULL CHECK (to_status IN ('draft','approved','retired')),
  actor_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  note TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
