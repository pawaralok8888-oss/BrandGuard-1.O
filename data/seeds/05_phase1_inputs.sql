-- Structured Phase 1 intake requirements and uploaded-guideline test fixtures.
-- Source material is mock/demo content; placeholders are not approved brand facts.
BEGIN;

INSERT INTO intake_specs
    (spec_key, version, source_file, description, status_values)
VALUES
    ('brand_intake', 1, 'intake_requirements.json',
     'Required-field intake spec. Each field is a slot the brand must fill. Fields with no approved rule show as ''not entered'' in the gap report. ''required'' means the brand must either upload a document covering it or answer ''not applicable'' or ''do not have this''.',
     '["entered", "not_entered", "not_applicable", "do_not_have"]'::jsonb)
ON CONFLICT (spec_key, version) DO UPDATE SET
    source_file = EXCLUDED.source_file,
    description = EXCLUDED.description,
    status_values = EXCLUDED.status_values;

INSERT INTO intake_categories
    (spec_key, spec_version, category_key, label, asset_types, checker_types, sort_order)
VALUES
    ('brand_intake', 1, 'product_specification', 'Product specification',
     '["product_image", "product_label", "campaign_idea", "social_post", "web_copy", "ad_copy"]'::jsonb,
     '["exact_value", "required_text", "rule"]'::jsonb, 1),
    ('brand_intake', 1, 'legal_regulatory', 'Legal and regulatory',
     '["any"]'::jsonb,
     '["required_text", "rule", "evidence_link"]'::jsonb, 2),
    ('brand_intake', 1, 'visual_identity', 'Visual identity',
     '["any_visual", "product_image", "product_label", "packaging_design"]'::jsonb,
     '["color_code", "font_check", "contrast", "image_rule"]'::jsonb, 3),
    ('brand_intake', 1, 'tone_of_voice', 'Tone of voice',
     '["social_post", "caption", "email", "web_copy", "ad_copy", "creator_script", "video_script", "campaign_idea"]'::jsonb,
     '["banned_phrase", "llm_semantic"]'::jsonb, 4),
    ('brand_intake', 1, 'content_creators', 'Content creators',
     '["creator_script", "creator_brief", "video_script", "video_asset"]'::jsonb,
     '["required_text", "llm_semantic", "manual_review"]'::jsonb, 5),
    ('brand_intake', 1, 'packaging', 'Packaging',
     '["packaging_design", "packaging_copy"]'::jsonb,
     '["required_text", "image_rule", "exact_value"]'::jsonb, 6),
    ('brand_intake', 1, 'marketing', 'Marketing',
     '["campaign_idea", "promo", "ad_copy", "social_post", "email"]'::jsonb,
     '["rule", "exact_value", "llm_semantic"]'::jsonb, 7)
ON CONFLICT (spec_key, spec_version, category_key) DO UPDATE SET
    label = EXCLUDED.label,
    asset_types = EXCLUDED.asset_types,
    checker_types = EXCLUDED.checker_types,
    sort_order = EXCLUDED.sort_order;

INSERT INTO intake_fields
    (spec_key, spec_version, category_key, field_key, label, field_type, required, check_type, column_names, sort_order)
VALUES
    ('brand_intake', 1, 'product_specification', 'sku_names', 'SKU names', 'list', TRUE, 'exact_name', '[]'::jsonb, 1),
    ('brand_intake', 1, 'product_specification', 'spf_per_sku', 'SPF per SKU', 'table', TRUE, 'exact_value', '["sku", "spf"]'::jsonb, 2),
    ('brand_intake', 1, 'product_specification', 'pa_per_sku', 'PA rating per SKU', 'table', TRUE, 'exact_value', '["sku", "pa"]'::jsonb, 3),
    ('brand_intake', 1, 'product_specification', 'water_resistance_duration', 'Water resistance duration per SKU', 'table', FALSE, 'exact_value', '["sku", "minutes"]'::jsonb, 4),
    ('brand_intake', 1, 'product_specification', 'active_ingredients', 'Active ingredients per SKU', 'table', TRUE, 'rule', '["sku", "ingredients"]'::jsonb, 5),
    ('brand_intake', 1, 'product_specification', 'reapplication_interval', 'Reapplication interval', 'text', TRUE, 'exact_value', '[]'::jsonb, 6),
    ('brand_intake', 1, 'product_specification', 'test_reports', 'Test reports with IDs', 'list', TRUE, 'evidence_link', '["report_id", "test", "date", "lab"]'::jsonb, 7),
    ('brand_intake', 1, 'product_specification', 'pack_sizes', 'Pack sizes per SKU', 'table', TRUE, 'exact_value', '["sku", "size"]'::jsonb, 8),
    ('brand_intake', 1, 'product_specification', 'launch_status', 'Launch status per SKU', 'table', TRUE, 'rule', '["sku", "status", "launch_date"]'::jsonb, 9),
    ('brand_intake', 1, 'legal_regulatory', 'markets', 'Markets sold in', 'list', TRUE, 'rule', '[]'::jsonb, 1),
    ('brand_intake', 1, 'legal_regulatory', 'mandatory_warnings', 'Mandatory warnings per market', 'table', TRUE, 'required_text', '["market", "warning_text"]'::jsonb, 2),
    ('brand_intake', 1, 'legal_regulatory', 'prohibited_claims', 'Prohibited claims', 'list', TRUE, 'banned_phrase', '[]'::jsonb, 3),
    ('brand_intake', 1, 'legal_regulatory', 'certifications', 'Certification numbers with expiry dates', 'table', TRUE, 'expiry', '["certification", "number", "expiry_date"]'::jsonb, 4),
    ('brand_intake', 1, 'legal_regulatory', 'advertising_code', 'Advertising code the brand follows', 'text', TRUE, 'rule', '[]'::jsonb, 5),
    ('brand_intake', 1, 'visual_identity', 'logo_files', 'Logo files and versions', 'file', TRUE, 'logo_match', '[]'::jsonb, 1),
    ('brand_intake', 1, 'visual_identity', 'clear_space', 'Clear-space rules', 'text', TRUE, 'manual_review', '[]'::jsonb, 2),
    ('brand_intake', 1, 'visual_identity', 'hex_values', 'HEX colour values', 'table', TRUE, 'color_code', '["name", "hex"]'::jsonb, 3),
    ('brand_intake', 1, 'visual_identity', 'pantone_values', 'Pantone values', 'table', FALSE, 'color_code', '["name", "pantone"]'::jsonb, 4),
    ('brand_intake', 1, 'visual_identity', 'fonts', 'Fonts with licence status', 'table', TRUE, 'font_check', '["font", "use", "license_status"]'::jsonb, 5),
    ('brand_intake', 1, 'visual_identity', 'imagery_rules', 'Imagery rules', 'text', TRUE, 'manual_review', '[]'::jsonb, 6),
    ('brand_intake', 1, 'tone_of_voice', 'voice_description', 'Voice description', 'text', TRUE, 'llm_semantic', '[]'::jsonb, 1),
    ('brand_intake', 1, 'tone_of_voice', 'approved_phrases', 'Approved phrases', 'list', FALSE, 'reference', '[]'::jsonb, 2),
    ('brand_intake', 1, 'tone_of_voice', 'banned_phrases', 'Banned phrases', 'list', TRUE, 'banned_phrase', '[]'::jsonb, 3),
    ('brand_intake', 1, 'tone_of_voice', 'good_examples', 'Example good copy', 'list', FALSE, 'reference', '[]'::jsonb, 4),
    ('brand_intake', 1, 'tone_of_voice', 'bad_examples', 'Example bad copy', 'list', FALSE, 'reference', '[]'::jsonb, 5),
    ('brand_intake', 1, 'content_creators', 'disclosure_wording', 'Disclosure wording', 'text', TRUE, 'required_text', '[]'::jsonb, 1),
    ('brand_intake', 1, 'content_creators', 'approved_creators', 'Approved creators', 'list', TRUE, 'approved_list', '[]'::jsonb, 2),
    ('brand_intake', 1, 'content_creators', 'repost_usage_rights', 'Usage rights for reposting', 'text', TRUE, 'manual_review', '[]'::jsonb, 3),
    ('brand_intake', 1, 'content_creators', 'script_approval_process', 'Script approval process', 'text', TRUE, 'manual_review', '[]'::jsonb, 4),
    ('brand_intake', 1, 'packaging', 'dielines', 'Dielines', 'file', TRUE, 'manual_review', '[]'::jsonb, 1),
    ('brand_intake', 1, 'packaging', 'mandatory_panel_text', 'Mandatory panel text', 'list', TRUE, 'required_text', '[]'::jsonb, 2),
    ('brand_intake', 1, 'packaging', 'recycling_symbols', 'Recycling symbols and rules', 'text', TRUE, 'rule', '[]'::jsonb, 3),
    ('brand_intake', 1, 'packaging', 'barcode_area', 'Barcode area dimensions', 'text', TRUE, 'image_rule', '[]'::jsonb, 4),
    ('brand_intake', 1, 'packaging', 'print_specs', 'Print specs', 'text', TRUE, 'manual_review', '[]'::jsonb, 5),
    ('brand_intake', 1, 'marketing', 'approved_offers', 'Approved offers', 'table', TRUE, 'expiry', '["offer", "terms", "start", "end"]'::jsonb, 1),
    ('brand_intake', 1, 'marketing', 'promo_calendar', 'Promo calendar', 'table', TRUE, 'expiry', '["promo", "start", "end"]'::jsonb, 2),
    ('brand_intake', 1, 'marketing', 'competitor_comparison_policy', 'Competitor comparison policy', 'text', TRUE, 'llm_semantic', '[]'::jsonb, 3),
    ('brand_intake', 1, 'marketing', 'approval_owner', 'Approval owner', 'text', TRUE, 'reference', '[]'::jsonb, 4)
ON CONFLICT (spec_key, spec_version, category_key, field_key) DO UPDATE SET
    label = EXCLUDED.label,
    field_type = EXCLUDED.field_type,
    required = EXCLUDED.required,
    check_type = EXCLUDED.check_type,
    column_names = EXCLUDED.column_names,
    sort_order = EXCLUDED.sort_order;

-- Replace the previous optional-file seed with categories defined by the required intake spec.
DELETE FROM guideline_categories
WHERE category_key NOT IN (
    'product_specification',
    'legal_regulatory',
    'visual_identity',
    'tone_of_voice',
    'content_creators',
    'packaging',
    'marketing'
);

INSERT INTO guideline_categories
    (category_key, label, applies_to, checker, source_file, sort_order, asset_types, checker_types)
VALUES
    ('product_specification', 'Product specification',
     '["product_image", "product_label", "campaign_idea", "social_post", "web_copy", "ad_copy"]'::jsonb,
     'exact_value, required_text, rule', 'intake_requirements.json', 1,
     '["product_image", "product_label", "campaign_idea", "social_post", "web_copy", "ad_copy"]'::jsonb,
     '["exact_value", "required_text", "rule"]'::jsonb),
    ('legal_regulatory', 'Legal and regulatory',
     '["any"]'::jsonb, 'required_text, rule, evidence_link', 'intake_requirements.json', 2,
     '["any"]'::jsonb, '["required_text", "rule", "evidence_link"]'::jsonb),
    ('visual_identity', 'Visual identity',
     '["any_visual", "product_image", "product_label", "packaging_design"]'::jsonb,
     'color_code, font_check, contrast, image_rule', 'intake_requirements.json', 3,
     '["any_visual", "product_image", "product_label", "packaging_design"]'::jsonb,
     '["color_code", "font_check", "contrast", "image_rule"]'::jsonb),
    ('tone_of_voice', 'Tone of voice',
     '["social_post", "caption", "email", "web_copy", "ad_copy", "creator_script", "video_script", "campaign_idea"]'::jsonb,
     'banned_phrase, llm_semantic', 'intake_requirements.json', 4,
     '["social_post", "caption", "email", "web_copy", "ad_copy", "creator_script", "video_script", "campaign_idea"]'::jsonb,
     '["banned_phrase", "llm_semantic"]'::jsonb),
    ('content_creators', 'Content creators',
     '["creator_script", "creator_brief", "video_script", "video_asset"]'::jsonb,
     'required_text, llm_semantic, manual_review', 'intake_requirements.json', 5,
     '["creator_script", "creator_brief", "video_script", "video_asset"]'::jsonb,
     '["required_text", "llm_semantic", "manual_review"]'::jsonb),
    ('packaging', 'Packaging',
     '["packaging_design", "packaging_copy"]'::jsonb,
     'required_text, image_rule, exact_value', 'intake_requirements.json', 6,
     '["packaging_design", "packaging_copy"]'::jsonb,
     '["required_text", "image_rule", "exact_value"]'::jsonb),
    ('marketing', 'Marketing',
     '["campaign_idea", "promo", "ad_copy", "social_post", "email"]'::jsonb,
     'rule, exact_value, llm_semantic', 'intake_requirements.json', 7,
     '["campaign_idea", "promo", "ad_copy", "social_post", "email"]'::jsonb,
     '["rule", "exact_value", "llm_semantic"]'::jsonb)
ON CONFLICT (category_key) DO UPDATE SET
    label = EXCLUDED.label,
    applies_to = EXCLUDED.applies_to,
    checker = EXCLUDED.checker,
    source_file = EXCLUDED.source_file,
    sort_order = EXCLUDED.sort_order,
    asset_types = EXCLUDED.asset_types,
    checker_types = EXCLUDED.checker_types;

INSERT INTO reference_documents
    (document_key, brand_name, document_type, source_file, source_format, is_mock, content_text, metadata)
VALUES
    ('dot_and_key_brand_guideline', 'Dot & Key', 'brand_guideline',
     'dot_and_key_brand_guideline.md', 'markdown', TRUE,
     $doc$# Dot & Key - Sunscreen Brand Guideline (Demo Set)

Status: Mock demo content for BrandGuard testing. This is not Dot & Key's official policy. Replace every value marked [PLACEHOLDER] with approved facts from the brand team before using the set in a real workflow.

## 1. Written copy (text_copy)

- Friendly, simple, sun-smart tone. Avoid fear-based wording ("your skin is ruined").
- No absolute protection claims: never "100% protection", "waterproof forever", "no white cast guaranteed".
- Say "broad spectrum" only with an approved test fact.
- SPF claims must match the approved SPF fact for that product: [PLACEHOLDER: SPF value per SKU].
- Use exact product names only. Do not shorten them.
- Avoid medical claims ("prevents skin cancer", "treats sunburn"). Use "helps protect skin from UV rays" only if supported by a fact.

## 2. Content creator guidelines (creator_brief)

- Creators must disclose paid partnerships clearly ("#ad" or "Paid partnership") in the first line of the caption and on video.
- Creators must use the product as directed in the brief. No claims beyond approved facts.
- Creators must not show a product being applied to a sunburned or damaged skin for demonstration.
- Reapplication advice must match the approved usage fact: [PLACEHOLDER: reapplication interval].
- No comparisons with named competitor products.
- Creators must share a draft script with the brand team 48 hours before posting.

## 3. Video and reels (video)

- First 3 seconds must show the product name or the brand logo.
- Every video that mentions SPF, UV protection or water resistance must include an on-screen disclaimer: [PLACEHOLDER: approved disclaimer text].
- Captions or subtitles are required on all video.
- No sunbathing or prolonged sun exposure shown without sun protection visible on screen.
- Music must be licensed for commercial use.
- Maximum 60 seconds for reels; no unlabelled jump cuts that hide product claims.

## 4. Product design (product_image)

- Product bottles and tubes use the approved colour palette: [PLACEHOLDER: primary and secondary HEX codes].
- Product images must show the actual SKU. No mock-ups presented as real product photos.
- Text on packs must be at least 6 pt (print) or 16 px (digital) and meet WCAG AA contrast (4.5:1).
- No logo stretching, recolouring or cropping. Use the approved logo file only.

## 5. Packaging (packaging_design)

- Mandatory on every pack: product name, SPF value, PA rating, net weight, usage direction, warning text, batch code area.
- [PLACEHOLDER: exact warning text required by regulator for the target market].
- Packaging copy must match approved facts word for word.
- Recyclability claims need evidence: [PLACEHOLDER: recyclability fact ID]. Otherwise do not use them.
- No child-appealing characters on sun protection packs.

## 6. Marketing ideas and campaigns (marketing_ideas)

- Campaign ideas must sell the benefit, not fear of the sun.
- Seasonal campaigns (summer, travel, monsoon) must have approved promo dates and terms.
- Discount codes and offers must match the live approved offer fact. No expired offers.
- Influencer or ambassador claims follow the Content creator section.
- New campaign ideas must be submitted to Brand review before any spend or outreach.

## 7. Visual identity (visual_identity)

- Logo: latest approved version only. [PLACEHOLDER: logo version and file name]
- Primary colour: [PLACEHOLDER HEX]
- Secondary colour: [PLACEHOLDER HEX]
- Headings font: [PLACEHOLDER]. Body font: [PLACEHOLDER].
- Alt text required on all images.
- Minimum contrast: WCAG AA (4.5:1 for normal text).

## 8. Claims and legal (claims_legal)

- Every claim needs a linked approved fact ID before publication.
- Confidential names (unreleased SKUs, internal project names) must never appear in public or creator materials.
- Prices and offers must be live and match the approved fact.

## 9. Custom categories (custom)

Brand teams can add categories here (for example "Influencer contracts", "Retail partner displays"). Each new category needs: label, the asset types it covers, and a checker type.

Mock document for demo purposes; the rules are illustrative placeholders, not actual brand standards.$doc$,
     '{"contains_placeholders":true,"official_policy":false}'::jsonb),
    ('dot_and_key_claims_test', 'Dot & Key', 'claims_test',
     'dot_and_key_claims_test.md', 'markdown', TRUE,
     $doc$# Dot & Key Sunscreen: Claims and Legal (Test Upload)

Mock rules for testing. Dot & Key is a real brand; these values are placeholders.

1. Absolute protection claims (Critical): Never use "100% protection", "100% of UV rays", "waterproof forever", "blocks all UV" or "no white cast guaranteed".
2. Medical claims (Critical): Never say the product "prevents skin cancer", "treats sunburn", "cures" or "heals" skin conditions.
3. Reapplication (Warning): Reapplication advice must match the approved usage fact: [PLACEHOLDER: interval]. Do not state a different interval in any post.
4. Required disclaimer (Warning): Any sunscreen benefit claim on Instagram or Ad must include: "Results may vary. Individual skin types may respond differently."
5. Creator disclosure (Critical): Paid creator posts must start with "#ad" or "Paid partnership".$doc$,
     '{"contains_placeholders":true,"official_policy":false}'::jsonb),
    ('dot_and_key_spec_pdf', 'Dot & Key', 'spec_test',
     'dot_and_key_spec_test.pdf', 'pdf', TRUE,
     $doc$Dot & Key Sunscreen: Packaging and Product Specification (Test Upload)
Mock rules for testing. Dot & Key is a real brand; these values are placeholders.
1. Product name. Always use the exact name "Dot & Key Sunscreen" with the SKU name on pack.
2. SPF on pack. The SPF value on the front panel must match the approved SPF fact for that SKU: [PLACEHOLDER: SPF per SKU].
3. Minimum font size. Warning text on pack must be at least 6 pt in print.
4. Colour. Primary brand colour: [PLACEHOLDER HEX]. Use only approved colours on packaging.
5. Warning text. Mandatory warning text for India: [PLACEHOLDER: regulator text].$doc$,
     '{"contains_placeholders":true,"official_policy":false,"extracted_text":true}'::jsonb),
    ('dot_and_key_spec_docx', 'Dot & Key', 'spec_test',
     'dot_and_key_spec_test.docx', 'docx', TRUE,
     $doc$Dot & Key Sunscreen: Packaging and Product Specification (Test Upload)
Mock rules for testing. Dot & Key is a real brand; these values are placeholders.
1. Product name. Always use the exact name "Dot & Key Sunscreen" with the SKU name on pack.
2. SPF on pack. The SPF value on the front panel must match the approved SPF fact for that SKU: [PLACEHOLDER: SPF per SKU].
3. Minimum font size. Warning text on pack must be at least 6 pt in print.
4. Colour. Primary brand colour: [PLACEHOLDER HEX]. Use only approved colours on packaging.
5. Warning text. Mandatory warning text for India: [PLACEHOLDER: regulator text].$doc$,
     '{"contains_placeholders":true,"official_policy":false,"extracted_text":true}'::jsonb)
ON CONFLICT (document_key) DO UPDATE SET
    brand_name = EXCLUDED.brand_name,
    document_type = EXCLUDED.document_type,
    source_file = EXCLUDED.source_file,
    source_format = EXCLUDED.source_format,
    is_mock = EXCLUDED.is_mock,
    content_text = EXCLUDED.content_text,
    metadata = EXCLUDED.metadata;

INSERT INTO guideline_test_cases
    (case_id, brand_name, channel, source_guideline_file, source_document_available, source_test_file, body_text, expected_findings, sort_order)
VALUES
    ('gg-01', 'GreenGlow', 'Instagram', 'greenglow_brand_guideline.md', FALSE, 'uploaded_guideline_test_set.json',
     $$GreenGlow Tea Tree Face Wash gives you 100% clear skin overnight. Guaranteed!$$,
     '[{"clause":"GG-2 absolute and medical claims","phrase":"100% clear skin","severity":"critical"},{"clause":"GG-2 absolute and medical claims","phrase":"overnight","severity":"critical"}]'::jsonb, 1),
    ('gg-02', 'GreenGlow', 'Website', 'greenglow_brand_guideline.md', FALSE, 'uploaded_guideline_test_set.json',
     $$Our best ever cleanser is the number one choice for customers with oily skin.$$,
     '[{"clause":"GG-3 unsupported superlatives","phrase":"best ever","severity":"warning"},{"clause":"GG-3 unsupported superlatives","phrase":"number one","severity":"warning"}]'::jsonb, 2),
    ('gg-03', 'GreenGlow', 'Email', 'greenglow_brand_guideline.md', FALSE, 'uploaded_guideline_test_set.json',
     $$Thanks for choosing us! Our clients love the new GreenGlow Moisturizer+. Results may vary.$$,
     '[{"clause":"GG-4 customer terminology","phrase":"clients","severity":"info"},{"clause":"GG-4 approved product names","phrase":"GreenGlow Moisturizer+","severity":"warning"}]'::jsonb, 3),
    ('gg-04', 'GreenGlow', 'Instagram', 'greenglow_brand_guideline.md', FALSE, 'uploaded_guideline_test_set.json',
     $$Our GreenGlow Cleansing Milk helps soothe sensitive skin after a long day.$$,
     '[{"clause":"GG-5 required disclaimer","phrase":"(missing) Results may vary. Individual skin types may respond differently.","severity":"warning"}]'::jsonb, 4),
    ('gg-05', 'GreenGlow', 'Ad', 'greenglow_brand_guideline.md', FALSE, 'uploaded_guideline_test_set.json',
     $$Try Project Aurora, our secret new serum, coming to shelves in March. Results may vary. Individual skin types may respond differently.$$,
     '[{"clause":"GG-7 confidential names","phrase":"Project Aurora","severity":"critical"}]'::jsonb, 5),
    ('gg-06', 'GreenGlow', 'Website', 'greenglow_brand_guideline.md', FALSE, 'uploaded_guideline_test_set.json',
     $$Summer offer: get 50% off GreenGlow Cleansing Milk with code SUMMER90, ends yesterday. Results may vary. Individual skin types may respond differently.$$,
     '[{"clause":"GG-6 prices and offers","phrase":"ends yesterday / expired offer","severity":"critical"}]'::jsonb, 6),
    ('gg-07', 'GreenGlow', 'Instagram', 'greenglow_brand_guideline.md', FALSE, 'uploaded_guideline_test_set.json',
     $$Real customer Sara says her skin was cured in a week! Results may vary. Individual skin types may respond differently.$$,
     '[{"clause":"GG-2 absolute and medical claims","phrase":"cured","severity":"critical"},{"clause":"GG-8 testimonials","phrase":"Real customer Sara","severity":"warning"}]'::jsonb, 7),
    ('gg-clean-01', 'GreenGlow', 'Website', 'greenglow_brand_guideline.md', FALSE, 'uploaded_guideline_test_set.json',
     $$GreenGlow Tea Tree Face Wash is a gentle daily cleanser for customers with combination skin. Results may vary. Individual skin types may respond differently.$$,
     '[]'::jsonb, 8),
    ('dk-01', 'Dot & Key', 'Instagram', 'dot_and_key_brand_guideline.md', TRUE, 'uploaded_guideline_test_set.json',
     $$Dot & Key sunscreen blocks 100% of UV rays, waterproof forever. Results may vary.$$,
     '[{"clause":"DK-1 absolute protection claims","phrase":"100% of UV rays","severity":"critical"},{"clause":"DK-1 absolute protection claims","phrase":"waterproof forever","severity":"critical"}]'::jsonb, 9),
    ('dk-02', 'Dot & Key', 'Ad', 'dot_and_key_brand_guideline.md', TRUE, 'uploaded_guideline_test_set.json',
     $$This sunscreen prevents skin cancer and treats sunburn in minutes.$$,
     '[{"clause":"DK-1 medical claims","phrase":"prevents skin cancer","severity":"critical"},{"clause":"DK-1 medical claims","phrase":"treats sunburn","severity":"critical"}]'::jsonb, 10),
    ('dk-03', 'Dot & Key', 'Instagram', 'dot_and_key_brand_guideline.md', TRUE, 'uploaded_guideline_test_set.json',
     $$Loved my Dot & Key sunscreen! Use it every 8 hours for best results. #ad$$,
     '[{"clause":"DK-2 creator reapplication advice","phrase":"every 8 hours","severity":"warning","note":"Must match approved usage fact, which is a placeholder in the mock; flag for review."}]'::jsonb, 11),
    ('dk-clean-01', 'Dot & Key', 'Website', 'dot_and_key_brand_guideline.md', TRUE, 'uploaded_guideline_test_set.json',
     $$Dot & Key Sunscreen helps protect skin from UV rays. Results may vary. Individual skin types may respond differently.$$,
     '[]'::jsonb, 12)
ON CONFLICT (case_id) DO UPDATE SET
    brand_name = EXCLUDED.brand_name,
    channel = EXCLUDED.channel,
    source_guideline_file = EXCLUDED.source_guideline_file,
    source_document_available = EXCLUDED.source_document_available,
    source_test_file = EXCLUDED.source_test_file,
    body_text = EXCLUDED.body_text,
    expected_findings = EXCLUDED.expected_findings,
    sort_order = EXCLUDED.sort_order;

COMMIT;
