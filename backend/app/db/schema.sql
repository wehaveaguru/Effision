-- 1. Enable pgvector extension
create extension if not exists vector;

-- 2. Create documents table with 384 dimensions
create table if not exists documents (
    id bigint primary key generated always as identity,
    content text not null,
    metadata jsonb default '{}'::jsonb,
    embedding vector(384)
);

-- 3. Create an HNSW index for fast cosine similarity search
create index if not exists documents_embedding_hnsw_idx 
on documents using hnsw (embedding vector_cosine_ops);

-- 4. Disable RLS so the anon/service key can insert freely
--    (fine for a hackathon; re-enable + add policies before going to prod)
alter table documents disable row level security;

-- 5. Create the match RPC function
create or replace function match_documents (
  query_embedding vector(384),
  match_threshold float default 0.3,
  match_count int default 5
)
returns table (
  id bigint,
  content text,
  metadata jsonb,
  similarity float
)
language sql stable
as $$
  select
    documents.id,
    documents.content,
    documents.metadata,
    1 - (documents.embedding <=> query_embedding) as similarity
  from documents
  where 1 - (documents.embedding <=> query_embedding) > match_threshold
  order by similarity desc
  limit match_count;
$$;