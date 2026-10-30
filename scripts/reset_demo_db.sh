#!/usr/bin/env bash
# scripts/reset_demo_db.sh
# Resets the local BrandGuard development database in Docker and applies seeds in order.

set -euo pipefail

FORCE=false
for arg in "$@"; do
  if [ "$arg" = "-f" ] || [ "$arg" = "--force" ] || [ "$arg" = "-y" ]; then
    FORCE=true
  fi
done

if [ "$FORCE" = false ]; then
  read -r -p "Reset local demo database? This will truncate demo tables and reapply seeds (y/N) " confirm
  if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Aborted."
    exit 0
  fi
fi

echo "Resetting BrandGuard demo database..."

CONTAINER="${CONTAINER_NAME:-brandguard-db}"
DB_USER="${POSTGRES_USER:-brandguard}"
DB_NAME="${POSTGRES_DB:-brandguard}"

# 1. Truncate demo tables (preserving embeddings table per schema specification)
docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 << 'EOF'
TRUNCATE TABLE
  alerts,
  notification_log,
  comments,
  decisions,
  findings,
  check_runs,
  fact_content_links,
  revisions,
  content_versions,
  content,
  guideline_versions,
  guidelines,
  fact_versions,
  facts,
  rule_patterns,
  assets,
  sample_drafts,
  glossary,
  products,
  users,
  teams,
  ai_calls,
  ai_cache
CASCADE;
EOF

# 2. Apply schema and seed files in order
SEED_FILES=(
  "data/schema.sql"
  "data/seeds/01_foundation.sql"
  "data/seeds/02_demo_people_products.sql"
  "data/seeds/03_demo_facts_guidelines.sql"
  "data/seeds/04_living.sql"
  "data/seeds/04b_demo_posts.sql"
  "data/seeds/05_phase1_inputs.sql"
)

for file in "${SEED_FILES[@]}"; do
  echo "Loading $file..."
  docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < "$file"
done

# 3. Print row counts
echo ""
echo "Database reset complete. Row counts:"
docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -A -F ": " << 'EOF'
SELECT 'users' AS table_name, count(*) AS count FROM users
UNION ALL SELECT 'teams', count(*) FROM teams
UNION ALL SELECT 'products', count(*) FROM products
UNION ALL SELECT 'facts', count(*) FROM facts
UNION ALL SELECT 'guidelines', count(*) FROM guidelines
UNION ALL SELECT 'content', count(*) FROM content;
EOF
