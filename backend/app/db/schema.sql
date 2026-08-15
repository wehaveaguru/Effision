-- Product Brain — nodes/edges graph schema
-- Design rule: every edge is a PROPOSAL until a human approves it.
-- confidence and source_document_id are NOT NULL on edges: provenance is
-- structurally enforced, not a convention.

create extension if not exists vector;
create extension if not exists pg_trgm;

-- ---------------------------------------------------------------------
-- Nodes
-- ---------------------------------------------------------------------
create table if not exists nodes (
    id              uuid primary key default gen_random_uuid(),
    node_type       text not null check (node_type in ('Product','Attribute','Category','Supplier','Source')),
    label           text not null,
    properties      jsonb not null default '{}'::jsonb,
    created_at      timestamptz not null default now()
);

create index if not exists idx_nodes_type on nodes(node_type);
create index if not exists idx_nodes_properties on nodes using gin(properties);

-- ---------------------------------------------------------------------
-- Source documents (parsed input files)
-- ---------------------------------------------------------------------
create table if not exists source_documents (
    id              uuid primary key default gen_random_uuid(),
    file_name       text not null,
    file_type       text not null,
    raw_text        text,
    parsed_at       timestamptz not null default now(),
    embedding       vector(1536)
);

create index if not exists idx_source_documents_fts
    on source_documents using gin (to_tsvector('english', coalesce(raw_text, '')));

-- ---------------------------------------------------------------------
-- Edges — the core provenance-carrying object
-- ---------------------------------------------------------------------
create table if not exists edges (
    id                  uuid primary key default gen_random_uuid(),
    source_node_id      uuid not null references nodes(id) on delete cascade,
    target_node_id      uuid not null references nodes(id) on delete cascade,
    relation            text not null,               -- e.g. 'has_attribute', 'belongs_to_category', 'supplied_by'
    value               jsonb,                        -- extracted value payload, e.g. {"diameter_mm": 8}
    confidence          numeric(4,3) not null check (confidence >= 0 and confidence <= 1),
    source_document_id  uuid not null references source_documents(id),
    status              text not null default 'proposed' check (status in ('proposed','approved','rejected')),
    reviewed_by         text,
    reviewed_at         timestamptz,
    created_at          timestamptz not null default now()
);

create index if not exists idx_edges_status on edges(status);
create index if not exists idx_edges_confidence on edges(confidence);
create index if not exists idx_edges_source_doc on edges(source_document_id);

-- ---------------------------------------------------------------------
-- RPCs used by app/pipeline/retrieve.py for hybrid search
-- (Supabase exposes Postgres functions as callable RPCs)
-- ---------------------------------------------------------------------

-- Vector similarity search over source_documents
create or replace function match_source_documents(
    query_embedding vector(1536),
    match_count int default 10
)
returns table (id uuid, file_name text, raw_text text, similarity float)
language sql stable
as $$
    select id, file_name, raw_text,
           1 - (embedding <=> query_embedding) as similarity
    from source_documents
    where embedding is not null
    order by embedding <=> query_embedding
    limit match_count;
$$;

-- Full text search over source_documents
create or replace function search_source_documents_fts(
    query_text text,
    match_count int default 10
)
returns table (id uuid, file_name text, raw_text text, rank float)
language sql stable
as $$
    select id, file_name, raw_text,
           ts_rank(to_tsvector('english', coalesce(raw_text, '')), plainto_tsquery('english', query_text)) as rank
    from source_documents
    where to_tsvector('english', coalesce(raw_text, '')) @@ plainto_tsquery('english', query_text)
    order by rank desc
    limit match_count;
$$;