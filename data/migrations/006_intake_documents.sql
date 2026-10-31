-- Phase 1: uploaded intake documents and the draft insights the LLM reads from them.
-- Idempotent: safe to run more than once. Apply to an existing database with:
--   psql "$DATABASE_URL" -f data/migrations/006_intake_documents.sql
CREATE SEQUENCE IF NOT EXISTS intake_document_seq;
CREATE SEQUENCE IF NOT EXISTS guideline_insight_seq;

CREATE TABLE IF NOT EXISTS intake_documents (
  id TEXT PRIMARY KEY DEFAULT 'DOC-' || lpad(nextval('intake_document_seq')::text, 3, '0'),
  category_id TEXT NOT NULL REFERENCES intake_categories(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
  size_bytes INTEGER NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 10485760),
  content BYTEA NOT NULL,
  extracted_text TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'ready', 'failed')),
  error_message TEXT NOT NULL DEFAULT '',
  uploaded_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS guideline_insights (
  id TEXT PRIMARY KEY DEFAULT 'INS-' || lpad(nextval('guideline_insight_seq')::text, 3, '0'),
  document_id TEXT NOT NULL REFERENCES intake_documents(id) ON DELETE CASCADE,
  field_id TEXT NOT NULL REFERENCES intake_fields(id) ON DELETE CASCADE,
  value TEXT NOT NULL,
  evidence TEXT NOT NULL DEFAULT '',
  confidence NUMERIC(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'rejected')),
  reviewed_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (document_id, field_id)
);

CREATE INDEX IF NOT EXISTS idx_intake_documents_category ON intake_documents(category_id);
CREATE INDEX IF NOT EXISTS idx_guideline_insights_field_status ON guideline_insights(field_id, status);
