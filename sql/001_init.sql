CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id text PRIMARY KEY,
    contour text NOT NULL,
    source_url text NOT NULL,
    title text NOT NULL,
    captured text,
    body_hash text NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id bigserial PRIMARY KEY,
    doc_id text NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    contour text NOT NULL,
    source_url text NOT NULL,
    heading_path text NOT NULL,
    content text NOT NULL,
    content_hash text NOT NULL UNIQUE,
    token_estimate integer NOT NULL,
    captured text,
    embedding vector(1536) NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('russian', content)) STORED
);

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS chunks_tsv_gin ON chunks USING gin (tsv);

CREATE INDEX IF NOT EXISTS chunks_contour_idx ON chunks (contour);

CREATE TABLE IF NOT EXISTS messages (
    id bigserial PRIMARY KEY,
    chat_id bigint NOT NULL,
    role text NOT NULL,
    content text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS messages_chat_idx ON messages (chat_id, id DESC);

CREATE TABLE IF NOT EXISTS dialog_log (
    id bigserial PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    chat_id bigint,
    refused boolean NOT NULL,
    source_urls text NOT NULL DEFAULT '',
    contour text,
    input_tokens integer NOT NULL DEFAULT 0,
    cached_tokens integer NOT NULL DEFAULT 0,
    output_tokens integer NOT NULL DEFAULT 0,
    embedding_tokens integer NOT NULL DEFAULT 0,
    cost_usd numeric(12, 6) NOT NULL DEFAULT 0,
    index_version text,
    latency_ms integer
);

CREATE TABLE IF NOT EXISTS leads (
    id bigserial PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    chat_id bigint NOT NULL,
    name text NOT NULL,
    company text NOT NULL,
    role_name text NOT NULL,
    task text NOT NULL,
    contact text NOT NULL DEFAULT '',
    consent boolean NOT NULL,
    delivered boolean NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS api_usage (
    id bigserial PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    kind text NOT NULL,
    chat_id bigint,
    input_tokens integer NOT NULL DEFAULT 0,
    cached_tokens integer NOT NULL DEFAULT 0,
    output_tokens integer NOT NULL DEFAULT 0,
    embedding_tokens integer NOT NULL DEFAULT 0,
    cost_usd numeric(12, 6) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chat_state (
    chat_id bigint PRIMARY KEY,
    disclaimer_shown boolean NOT NULL DEFAULT false,
    lead_step text,
    lead_draft jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS crawl_status (
    source_url text PRIMARY KEY,
    last_success timestamptz,
    last_error text
);

CREATE TABLE IF NOT EXISTS settings (
    key text PRIMARY KEY,
    value text NOT NULL
);

CREATE TABLE IF NOT EXISTS index_meta (
    id integer PRIMARY KEY CHECK (id = 1),
    version text NOT NULL,
    built_at timestamptz NOT NULL DEFAULT now(),
    chunk_count integer NOT NULL
);
