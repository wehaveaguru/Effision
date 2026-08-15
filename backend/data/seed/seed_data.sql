-- Manual seed: 2-3 rows to validate the schema shape end-to-end
-- (Step 1 goal: "seed manually with 2-3 rows to validate query paths").
-- Run against a live Supabase/Postgres instance:
--   psql "$DATABASE_URL" -f data/seed/seed_data.sql

insert into source_documents (id, file_name, file_type, raw_text)
values (
    '00000000-0000-0000-0000-000000000001',
    'camber_bolt_specsheet.txt',
    'txt',
    'CAMBER SUPPLY CO. -- PRODUCT SPEC SHEET ... Diameter: 8.0 mm ...'
);

insert into nodes (id, node_type, label, properties) values
    ('00000000-0000-0000-0000-000000000010', 'Product', 'Camber Hex Head Bolt M8x40 Grade 8.8', '{}'),
    ('00000000-0000-0000-0000-000000000011', 'Attribute', '8.0', '{"field_name": "diameter_mm"}'),
    ('00000000-0000-0000-0000-000000000012', 'Supplier', 'Camber Supply Co.', '{}');

insert into edges (source_node_id, target_node_id, relation, value, confidence, source_document_id, status) values
    (
        '00000000-0000-0000-0000-000000000010',
        '00000000-0000-0000-0000-000000000011',
        'has_attribute',
        '{"diameter_mm": 8.0}',
        0.95,
        '00000000-0000-0000-0000-000000000001',
        'proposed'
    ),
    (
        '00000000-0000-0000-0000-000000000010',
        '00000000-0000-0000-0000-000000000012',
        'supplied_by',
        '{"supplier": "Camber Supply Co."}',
        0.9,
        '00000000-0000-0000-0000-000000000001',
        'proposed'
    );