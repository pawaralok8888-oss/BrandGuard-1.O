-- Categories and channels are data, not code. Guidelines must use a known category.
-- Also records whether an uploaded content image is the brand logo (used by the logo check).
-- Idempotent: safe to run on a database that already has these changes.
CREATE TABLE IF NOT EXISTS guideline_categories (
  id TEXT PRIMARY KEY,
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS channels (
  id TEXT PRIMARY KEY,
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO guideline_categories (id, sort_order) VALUES
  ('Terminology', 1), ('Claims & Legal', 2), ('Tone of Voice', 3), ('Formatting', 4),
  ('Accessibility', 5), ('Brand Assets', 6), ('Security', 7)
ON CONFLICT (id) DO NOTHING;

INSERT INTO channels (id, sort_order) VALUES
  ('Website', 1), ('Instagram', 2), ('Email', 3), ('Ad', 4)
ON CONFLICT (id) DO NOTHING;

-- Every existing guideline must use a known category before the foreign key can be added.
ALTER TABLE guidelines DROP CONSTRAINT IF EXISTS guidelines_category_check;
ALTER TABLE guidelines DROP CONSTRAINT IF EXISTS guidelines_category_fkey;
ALTER TABLE guidelines ADD CONSTRAINT guidelines_category_fkey
  FOREIGN KEY (category) REFERENCES guideline_categories(id);

ALTER TABLE content ADD COLUMN IF NOT EXISTS image_is_logo BOOLEAN NOT NULL DEFAULT FALSE;
