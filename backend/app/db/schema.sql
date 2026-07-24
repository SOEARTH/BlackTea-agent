-- BlackTea 业务表 DDL (app schema)
-- LangGraph checkpoint 表留 public schema，由 PostgresSaver 自建。

CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.threads (
    id text PRIMARY KEY,
    user_id uuid REFERENCES app.users(id),
    title text,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.decision_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES app.users(id),
    thread_id text REFERENCES app.threads(id),
    requirement jsonb NOT NULL,
    report jsonb NOT NULL,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.profile_facts (
    id bigserial PRIMARY KEY,
    user_id uuid REFERENCES app.users(id),
    category text NOT NULL,
    key text NOT NULL,
    value text NOT NULL,
    confidence real DEFAULT 1.0,
    source text DEFAULT 'dialog',
    updated_at timestamptz DEFAULT now(),
    UNIQUE (user_id, category, key)
);

CREATE TABLE IF NOT EXISTS app.episodic_memories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES app.users(id),
    content text NOT NULL,
    milvus_id text NOT NULL,
    importance real DEFAULT 0.5,
    created_at timestamptz DEFAULT now(),
    last_recalled_at timestamptz
);
