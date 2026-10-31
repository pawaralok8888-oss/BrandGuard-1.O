-- Brand intake: the questions a brand must answer before checks are meaningful, and the gap report.
-- Each field names a coverage check. The report counts the real data for that check (assets,
-- products, facts, guidelines, rules). A person can also mark a field provided or not applicable.
-- Idempotent: safe to run on a database that already has these tables.
CREATE TABLE IF NOT EXISTS intake_categories (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS intake_fields (
  id TEXT PRIMARY KEY,
  category_id TEXT NOT NULL REFERENCES intake_categories(id) ON DELETE CASCADE,
  label TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  required BOOLEAN NOT NULL DEFAULT TRUE,
  coverage_check TEXT NOT NULL CHECK (coverage_check IN (
    'logo','colour_palette','fonts','product_list','certifications','offers',
    'tone_guideline','terminology_guideline','claims_guideline','accessibility_guideline',
    'brand_assets_guideline','prohibited_terms','disclaimers','confidential_terms','manual'
  )),
  sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS intake_responses (
  field_id TEXT PRIMARY KEY REFERENCES intake_fields(id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK (status IN ('provided','not_applicable')),
  note TEXT NOT NULL DEFAULT '',
  updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO intake_categories (id, label, sort_order) VALUES
  ('brand_identity', 'Brand identity', 1),
  ('products', 'Products and proof', 2),
  ('voice_and_terms', 'Voice and terms', 3),
  ('claims_and_legal', 'Claims and legal', 4),
  ('visuals', 'Visuals and accessibility', 5)
ON CONFLICT (id) DO NOTHING;

INSERT INTO intake_fields (id, category_id, label, description, required, coverage_check, sort_order) VALUES
  ('IF-001', 'brand_identity', 'Logo', 'An approved logo version in the asset library.', TRUE, 'logo', 1),
  ('IF-002', 'brand_identity', 'Colour palette', 'Approved brand colours with hex codes.', TRUE, 'colour_palette', 2),
  ('IF-003', 'brand_identity', 'Typefaces', 'Heading and body fonts.', TRUE, 'fonts', 3),
  ('IF-004', 'brand_identity', 'Brand owner and contact', 'Who approves brand changes.', TRUE, 'manual', 4),
  ('IF-005', 'products', 'Product list', 'Every product that may be named in content.', TRUE, 'product_list', 1),
  ('IF-006', 'products', 'Certifications', 'Current certifications with validity dates.', TRUE, 'certifications', 2),
  ('IF-007', 'products', 'Offers and prices', 'Current offers and prices, if content mentions them.', FALSE, 'offers', 3),
  ('IF-008', 'voice_and_terms', 'Tone of voice', 'How the brand should sound.', TRUE, 'tone_guideline', 1),
  ('IF-009', 'voice_and_terms', 'Approved terminology', 'Product and company names, and how to write them.', TRUE, 'terminology_guideline', 2),
  ('IF-010', 'voice_and_terms', 'Prohibited terms', 'Words and phrases content must not use, with replacements.', TRUE, 'prohibited_terms', 3),
  ('IF-011', 'voice_and_terms', 'Confidential terms', 'Internal names that must never reach the AI or the public.', TRUE, 'confidential_terms', 4),
  ('IF-012', 'claims_and_legal', 'Claims rules', 'What claims need evidence and what evidence is accepted.', TRUE, 'claims_guideline', 1),
  ('IF-013', 'claims_and_legal', 'Required disclaimers', 'Text that must appear on certain content.', TRUE, 'disclaimers', 2),
  ('IF-014', 'visuals', 'Accessibility rules', 'Contrast and alt text requirements.', TRUE, 'accessibility_guideline', 1),
  ('IF-015', 'visuals', 'Visual asset rules', 'Which images and layouts are allowed.', FALSE, 'brand_assets_guideline', 2)
ON CONFLICT (id) DO NOTHING;
