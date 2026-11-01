-- Adds the logo flag used by the logo check. Idempotent.
ALTER TABLE content
  ADD COLUMN IF NOT EXISTS image_is_logo BOOLEAN NOT NULL DEFAULT FALSE;
