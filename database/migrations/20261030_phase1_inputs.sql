-- Phase 1 intake and uploaded-guideline test data schema.
-- Safe to apply repeatedly; data is loaded by data/seeds/05_phase1_inputs.sql.
BEGIN;

ALTER TABLE content
    ADD COLUMN IF NOT EXISTS asset_type TEXT NOT NULL DEFAULT 'social_post';

UPDATE content
SET asset_type = 'social_post'
WHERE asset_type IS NULL OR asset_type = '';

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
    asset_types JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(asset_types) = 'array'),
    checker_types JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(checker_types) = 'array'),
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
        REFERENCES intake_categories(spec_key, spec_version, category_key)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS guideline_categories (
    category_key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    applies_to JSONB NOT NULL CHECK (jsonb_typeof(applies_to) = 'array'),
    checker TEXT NOT NULL,
    source_file TEXT NOT NULL,
    sort_order INTEGER NOT NULL CHECK (sort_order > 0),
    asset_types JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(asset_types) = 'array'),
    checker_types JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(checker_types) = 'array')
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
    document_type TEXT NOT NULL CHECK (
        document_type IN ('brand_guideline', 'claims_test', 'spec_test')
    ),
    source_file TEXT NOT NULL UNIQUE,
    source_format TEXT NOT NULL CHECK (source_format IN ('markdown', 'pdf', 'docx')),
    is_mock BOOLEAN NOT NULL DEFAULT TRUE,
    content_text TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE TABLE IF NOT EXISTS guideline_test_cases (
    case_id TEXT PRIMARY KEY,
    brand_name TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('Website', 'Instagram', 'Email', 'Ad')),
    source_guideline_file TEXT NOT NULL,
    source_document_available BOOLEAN NOT NULL,
    source_test_file TEXT NOT NULL,
    body_text TEXT NOT NULL,
    expected_findings JSONB NOT NULL
        CHECK (jsonb_typeof(expected_findings) = 'array'),
    sort_order INTEGER NOT NULL CHECK (sort_order > 0)
);

CREATE INDEX IF NOT EXISTS idx_intake_fields_order
    ON intake_fields(spec_key, spec_version, category_key, sort_order);
CREATE INDEX IF NOT EXISTS idx_guideline_test_cases_brand_channel
    ON guideline_test_cases(brand_name, channel, sort_order);

COMMIT;
