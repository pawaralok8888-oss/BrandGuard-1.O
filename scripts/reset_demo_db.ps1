# scripts/reset_demo_db.ps1
# Resets the local BrandGuard development database in Docker and applies seeds in order.

param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

if (-not $Force) {
    $confirm = Read-Host "Reset local demo database? This will truncate demo tables and reapply seeds (y/N)"
    if ($confirm -ne 'y' -and $confirm -ne 'Y') {
        Write-Host "Aborted."
        exit 0
    }
}

Write-Host "Resetting BrandGuard demo database..."

$container = "brandguard-db"
$user = "brandguard"
$db = "brandguard"

# 1. Truncate demo tables in dependency order (preserving embeddings table per schema specification)
$truncateSql = @"
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
"@

$truncateSql | docker exec -i $container psql -U $user -d $db -v ON_ERROR_STOP=1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to truncate tables."
    exit 1
}

# 2. Apply schema and seed files in order
$seedFiles = @(
    "data/schema.sql",
    "data/seeds/01_foundation.sql",
    "data/seeds/02_demo_people_products.sql",
    "data/seeds/03_demo_facts_guidelines.sql",
    "data/seeds/04_living.sql",
    "data/seeds/04b_demo_posts.sql"
)

foreach ($file in $seedFiles) {
    Write-Host "Loading $file..."
    Get-Content -Raw $file | docker exec -i $container psql -U $user -d $db -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed loading $file"
        exit 1
    }
}

# 3. Print row counts
Write-Host "`nDatabase reset complete. Row counts:"
$countSql = @"
SELECT 'users' AS table_name, count(*) AS count FROM users
UNION ALL SELECT 'teams', count(*) FROM teams
UNION ALL SELECT 'products', count(*) FROM products
UNION ALL SELECT 'facts', count(*) FROM facts
UNION ALL SELECT 'guidelines', count(*) FROM guidelines
UNION ALL SELECT 'content', count(*) FROM content;
"@

$countSql | docker exec -i $container psql -U $user -d $db -t -A -F ": "
