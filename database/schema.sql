-- ============================================================
-- Real Estate AI Agent (Aria) — Supabase Schema
-- Run this in Supabase SQL Editor
-- ============================================================

create extension if not exists vector;

-- 1. Customers / leads
create table if not exists customers (
    id uuid primary key default gen_random_uuid(),
    external_id text unique,
    name text,
    email text,
    phone text,
    language text default 'auto',
    tags text[] default '{}',
    metadata jsonb default '{}'::jsonb,   -- extracted lead details (budget, city, bedrooms, etc.)
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- 2. Conversations
create table if not exists conversations (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid references customers(id) on delete cascade,
    channel text default 'web',
    status text default 'open',
    started_at timestamptz default now(),
    last_message_at timestamptz default now(),
    summary text
);

-- 3. Messages
create table if not exists messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid references conversations(id) on delete cascade,
    role text not null,
    content text not null,
    intent text,
    sentiment text,
    sentiment_score numeric,
    language text,
    created_at timestamptz default now()
);

-- 4. Properties (the "knowledge base" for RAG — one row per listing)
create table if not exists properties (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    listing_type text default 'rent',      -- 'rent' | 'sale'
    address text,
    city text,
    neighborhood text,
    price numeric,
    bedrooms int,
    bathrooms numeric,
    sqft int,
    features text[] default '{}',          -- e.g. {'pet_friendly','parking','furnished'}
    description text,
    embedding vector(384),                 -- fastembed BAAI/bge-small-en-v1.5
    status text default 'available',       -- available | pending | leased | sold
    created_at timestamptz default now()
);

create index if not exists properties_embedding_idx
    on properties using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

-- 4b. General knowledge base (FAQs, neighborhood guides, policies — non-property content)
create table if not exists kb_documents (
    id uuid primary key default gen_random_uuid(),
    title text,
    content text not null,
    source text,
    embedding vector(384),
    created_at timestamptz default now()
);

create index if not exists kb_documents_embedding_idx
    on kb_documents using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

create or replace function match_kb_documents (
    query_embedding vector(384),
    match_count int default 4
)
returns table (
    id uuid,
    title text,
    content text,
    source text,
    similarity float
)
language sql stable
as $$
    select
        kb_documents.id, kb_documents.title, kb_documents.content, kb_documents.source,
        1 - (kb_documents.embedding <=> query_embedding) as similarity
    from kb_documents
    order by kb_documents.embedding <=> query_embedding
    limit match_count;
$$;

-- 5. Leads/tickets — qualified lead record for the sales/agent team
create table if not exists tickets (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid references conversations(id) on delete cascade,
    customer_id uuid references customers(id) on delete cascade,
    category text,                 -- buy | rent | financing | legal | complaint | general
    priority text default 'medium',
    priority_score numeric,
    status text default 'open',
    summary text,
    escalated boolean default false,
    escalated_reason text,
    assigned_agent text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- 6. Viewing slots (agent-defined availability)
create table if not exists viewing_slots (
    id uuid primary key default gen_random_uuid(),
    property_id uuid references properties(id) on delete cascade,
    slot_start timestamptz not null,
    slot_end timestamptz not null,
    is_booked boolean default false,
    created_at timestamptz default now()
);

-- 7. Viewings (confirmed bookings)
create table if not exists viewings (
    id uuid primary key default gen_random_uuid(),
    slot_id uuid references viewing_slots(id) on delete set null,
    property_id uuid references properties(id) on delete cascade,
    customer_id uuid references customers(id) on delete cascade,
    conversation_id uuid references conversations(id) on delete set null,
    scheduled_start timestamptz not null,
    scheduled_end timestamptz not null,
    status text default 'confirmed',   -- confirmed | cancelled | completed | no_show
    notes text,
    created_at timestamptz default now()
);

create index if not exists idx_messages_conversation on messages(conversation_id);
create index if not exists idx_conversations_customer on conversations(customer_id);
create index if not exists idx_tickets_status on tickets(status);
create index if not exists idx_tickets_priority on tickets(priority);
create index if not exists idx_properties_city on properties(city);
create index if not exists idx_viewing_slots_property on viewing_slots(property_id);
create index if not exists idx_viewing_slots_available on viewing_slots(is_booked);

-- Similarity search for property listings
create or replace function match_properties (
    query_embedding vector(384),
    match_count int default 4
)
returns table (
    id uuid,
    title text,
    listing_type text,
    address text,
    city text,
    neighborhood text,
    price numeric,
    bedrooms int,
    bathrooms numeric,
    sqft int,
    features text[],
    description text,
    status text,
    similarity float
)
language sql stable
as $$
    select
        properties.id, properties.title, properties.listing_type, properties.address,
        properties.city, properties.neighborhood, properties.price, properties.bedrooms,
        properties.bathrooms, properties.sqft, properties.features, properties.description,
        properties.status,
        1 - (properties.embedding <=> query_embedding) as similarity
    from properties
    where properties.status = 'available'
    order by properties.embedding <=> query_embedding
    limit match_count;
$$;
