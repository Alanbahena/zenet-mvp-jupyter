# Zenet Production Software — Data Model Overview v1

## Purpose

This document defines the data model for the Zenet production software. It builds on the MVP Gradio data model, extending it for multi-tenant SaaS, audit trails, authentication, and production-grade persistence via Supabase (PostgreSQL).

---

## Table of Contents

1. [MVP vs. Production — Key Differences](#mvp-vs-production--key-differences)
2. [Entity Relationship Diagram](#entity-relationship-diagram)
3. [Core Entities](#core-entities)
4. [Authentication & Multi-Tenancy](#authentication--multi-tenancy)
5. [Standardization Entities](#standardization-entities)
6. [Operational Entities](#operational-entities)
7. [AI & Session Entities](#ai--session-entities)
8. [Enumerations (Fixed Values)](#enumerations-fixed-values)
9. [Indexes & Performance](#indexes--performance)
10. [Row-Level Security (RLS)](#row-level-security-rls)
11. [Migration Strategy](#migration-strategy)
12. [Open Questions](#open-questions)

---

## MVP vs. Production — Key Differences

| Aspect | MVP (Gradio) | Production (Supabase) |
|--------|-------------|----------------------|
| Database | SQLite (single file) | PostgreSQL (Supabase managed) |
| Multi-tenancy | Single session, no tenant isolation | Row-Level Security per tenant |
| Auth | No auth — anyone can access | Supabase Auth (email/password, JWT) |
| IDs | Sequential integers (1, 2, 3...) | UUIDs |
| Timestamps | None | created_at, updated_at on all entities |
| Audit | None | created_by, updated_by user references |
| Soft deletes | None (hard delete only) | deleted_at column on all entities |
| Linking | Name-based resolution (Phase A) | Foreign key references (UUID) |
| Ingredients | Embedded list in Recipe dataclass | Separate recipe_ingredients table with FKs |
| Classification | JSON blob | Structured columns |
| Agent state | JSON blob per session | Structured conversation + state tables |
| Taxonomies | In-memory only, not persisted | Persisted in taxonomy tables |
| Registries | In-memory Python objects | Database queries with RLS |

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AUTHENTICATION & TENANCY                            │
│                                                                             │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────────┐                 │
│  │  tenant   │────▶│  restaurant  │     │  auth.users       │                │
│  │           │     │              │     │  (Supabase Auth)  │                │
│  └──────────┘     └──────────────┘     └──────────────────┘                 │
│       │                │                       │                            │
│       │                │                       │                            │
│       ▼                │                       ▼                            │
│  ┌──────────────────┐  │              ┌──────────────────┐                  │
│  │  tenant_member   │◀─┘              │     profile       │                 │
│  │  (user ↔ tenant) │◀────────────────│  (extends auth)   │                 │
│  └──────────────────┘                 └──────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONFIGURATION ENTITIES                              │
│                                                                             │
│  ┌───────────────┐  ┌────────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ recipe_unit   │  │ inventory_unit │  │category_recipe│  │family_inventory│ │
│  │               │  │  (self-ref)    │  │              │  │              │  │
│  └───────────────┘  └────────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         RECIPE & INVENTORY                                  │
│                                                                             │
│  ┌──────────┐     ┌──────────────────┐     ┌────────────────┐               │
│  │  recipe   │────▶│recipe_ingredient │────▶│ inventory_item │               │
│  │          │     │                  │     │                │               │
│  └──────────┘     └──────────────────┘     └────────────────┘               │
│       │                    │                      │                          │
│       │                    │                      │                          │
│       ▼                    ▼                      ▼                          │
│  category_recipe      recipe_unit          family_inventory                 │
│                                            inventory_unit (x2)              │
│                                            inventory_category               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         NORMALIZATION                                        │
│                                                                             │
│  ┌──────────────────────────┐     ┌──────────────────────┐                  │
│  │ recipe_unit_conversion   │     │  deduction_log        │                 │
│  │ (recipe ↔ inventory unit)│     │  (historical record)  │                 │
│  └──────────────────────────┘     └──────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         AI & SESSIONS                                       │
│                                                                             │
│  ┌──────────────────┐     ┌──────────────────┐                              │
│  │  conversation    │────▶│conversation_message│                             │
│  │  (per section)   │     │  (chat history)    │                             │
│  └──────────────────┘     └──────────────────┘                              │
│                                                                             │
│  ┌──────────────────┐     ┌──────────────────┐                              │
│  │  agent_state     │     │  classification   │                             │
│  │  (per section)   │     │  (structured)     │                             │
│  └──────────────────┘     └──────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Entities

### tenant

The top-level entity for multi-tenancy. One tenant = one restaurant business (may have multiple locations in the future).

```sql
CREATE TABLE tenant (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    slug          TEXT NOT NULL UNIQUE,        -- URL-friendly identifier
    plan          TEXT NOT NULL DEFAULT 'free', -- free, starter, pro
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**MVP equivalent:** Did not exist. Session was the implicit tenant.

---

### profile

Extends Supabase Auth's `auth.users` table with application-specific data. One row per authenticated user.

```sql
CREATE TABLE profile (
    id            UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name     TEXT NOT NULL,
    avatar_url    TEXT,
    phone         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**MVP equivalent:** `user` table (id, name, email, role). Auth was not implemented.

---

### tenant_member

Junction table linking users to tenants with roles. Supports one user belonging to multiple tenants (e.g., a consultant managing several restaurants).

```sql
CREATE TABLE tenant_member (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role          TEXT NOT NULL DEFAULT 'owner',  -- owner, admin, chef, staff
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    invited_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    accepted_at   TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(tenant_id, user_id)
);
```

**MVP equivalent:** `UserRegistry` with role in {admin, mesero, cocinero, inventario}. No multi-tenant support.

**Production roles:**
| Role | Description | Permissions |
|------|------------|-------------|
| owner | Restaurant owner, full access | Everything + billing + delete tenant |
| admin | Manager, can configure everything | Everything except billing |
| chef | Kitchen manager | Recipes, inventory, manual operativo |
| staff | Read-only operational access | View manual operativo, KPIs |

---

### restaurant

The restaurant profile. Each tenant has exactly one restaurant (v1). Multi-location support is a future extension.

```sql
CREATE TABLE restaurant (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    restaurant_type     TEXT NOT NULL,           -- Casual, Rapida, Gourmet, Cafeteria, Cafe
    description         TEXT,                    -- AI-generated classification description
    address             TEXT,
    city                TEXT,
    state               TEXT,
    country             TEXT DEFAULT 'Mexico',
    phone               TEXT,
    email               TEXT,
    website             TEXT,
    logo_url            TEXT,
    seating_capacity    INTEGER,
    operating_hours     JSONB,                   -- {"monday": {"open": "08:00", "close": "22:00"}, ...}
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(tenant_id)                            -- one restaurant per tenant (v1)
);
```

**MVP equivalent:** `Restaurant(id, name, address, restaurant_type_id, notes)`. Production adds address decomposition, contact info, operating hours, logo, and seating capacity.

**Key change:** `restaurant_type` is now a TEXT enum instead of FK to a fixed types table. The fixed list {Casual, Rapida, Gourmet, Cafeteria, Cafe} is enforced at application level via a CHECK constraint or validation.

---

## Authentication & Multi-Tenancy

### How it works

1. User signs up via Supabase Auth → row in `auth.users`
2. Trigger creates row in `profile` automatically
3. User creates a tenant (restaurant business) → row in `tenant`
4. User is added as `owner` in `tenant_member`
5. User creates a restaurant under that tenant → row in `restaurant`
6. All subsequent entities (recipes, inventory, etc.) reference `tenant_id`
7. RLS policies ensure users only see data for tenants they belong to

### JWT claims

Supabase JWT includes `user_id`. RLS policies join through `tenant_member` to determine access:

```sql
-- Example RLS policy
CREATE POLICY "Users can view their tenant's recipes"
ON recipe FOR SELECT
USING (
    tenant_id IN (
        SELECT tenant_id FROM tenant_member
        WHERE user_id = auth.uid()
        AND is_active = TRUE
    )
);
```

---

## Standardization Entities

All standardization entities include these common columns:

```sql
-- Common columns on every tenant-scoped table
tenant_id     UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
created_by    UUID REFERENCES auth.users(id),
updated_by    UUID REFERENCES auth.users(id),
deleted_at    TIMESTAMPTZ                        -- soft delete
```

---

### recipe_unit

Units used in recipe instructions (how the chef measures during cooking).

```sql
CREATE TABLE recipe_unit (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,                  -- "gramo", "cucharada", "porcion"
    symbol        TEXT NOT NULL,                  -- "g", "cdta", "pza"
    description   TEXT,
    is_standard   BOOLEAN NOT NULL DEFAULT FALSE, -- TRUE for g, kg, ml, L, pza
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by    UUID REFERENCES auth.users(id),
    deleted_at    TIMESTAMPTZ,

    UNIQUE(tenant_id, symbol) WHERE deleted_at IS NULL
);
```

**MVP equivalent:** `RecipeUnit(id, name, symbol, description)`. Production adds `is_standard`, `tenant_id`, soft delete, and audit fields.

---

### inventory_unit

Units used for inventory tracking and purchasing. Self-referential for equivalence chains (1 caja = 10 kg).

```sql
CREATE TABLE inventory_unit (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,              -- "kilogramo", "caja", "bolsa"
    symbol            TEXT NOT NULL,              -- "kg", "caja", "bolsa"
    description       TEXT,
    base_unit_id      UUID REFERENCES inventory_unit(id), -- self-referential chain
    factor_to_base    DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    is_standard       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by        UUID REFERENCES auth.users(id),
    deleted_at        TIMESTAMPTZ,

    UNIQUE(tenant_id, symbol) WHERE deleted_at IS NULL,
    CHECK(factor_to_base > 0)
);
```

**MVP equivalent:** Same structure. Production adds UUID, CHECK constraint, soft delete.

**Equivalence chain example:**
```
g (standard, base_unit_id=NULL, factor=1.0)
  └── kg (standard, base_unit_id=g, factor=1000)
      └── caja (non-standard, base_unit_id=kg, factor=10)
          → 1 caja = 10 kg = 10000 g
```

---

### category_recipe

Categories for organizing recipes (Entradas, Platos Fuertes, Bebidas, Postres, etc.).

```sql
CREATE TABLE category_recipe (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    description   TEXT,
    sort_order    INTEGER NOT NULL DEFAULT 0,     -- display ordering
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by    UUID REFERENCES auth.users(id),
    deleted_at    TIMESTAMPTZ,

    UNIQUE(tenant_id, name) WHERE deleted_at IS NULL
);
```

**MVP equivalent:** `CategoryRecipe(id, name, description)`. Production adds `sort_order` for UI ordering.

---

### family_inventory

Grouping for inventory items (Carnes, Lacteos, Verduras, Granos, Especias, etc.).

```sql
CREATE TABLE family_inventory (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    description   TEXT,
    base_unit_id  UUID REFERENCES inventory_unit(id), -- optional, for reporting
    sort_order    INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by    UUID REFERENCES auth.users(id),
    deleted_at    TIMESTAMPTZ,

    UNIQUE(tenant_id, name) WHERE deleted_at IS NULL
);
```

**MVP equivalent:** `FamilyInventory(id, name, description, base_unit_id)`. Production adds `sort_order`.

---

### inventory_item

An item in the restaurant's inventory. Has two units: stock (internal tracking) and purchase (how suppliers sell it).

```sql
CREATE TABLE inventory_item (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                 UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    name                      TEXT NOT NULL,
    description               TEXT,
    stock_unit_id             UUID NOT NULL REFERENCES inventory_unit(id),
    purchase_unit_id          UUID NOT NULL REFERENCES inventory_unit(id),
    purchase_to_stock_factor  DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    category                  TEXT NOT NULL DEFAULT 'perishable',  -- perishable, non_perishable
    family_id                 UUID REFERENCES family_inventory(id),
    min_stock_quantity        DOUBLE PRECISION,    -- NEW: low stock alert threshold
    current_stock_quantity    DOUBLE PRECISION,    -- NEW: current stock level
    cost_per_purchase_unit    DECIMAL(10,2),       -- NEW: last known purchase price
    supplier_name             TEXT,                -- NEW: primary supplier
    notes                     TEXT,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by                UUID REFERENCES auth.users(id),
    updated_by                UUID REFERENCES auth.users(id),
    deleted_at                TIMESTAMPTZ,

    UNIQUE(tenant_id, name) WHERE deleted_at IS NULL,
    CHECK(purchase_to_stock_factor > 0)
);
```

**MVP equivalent:** `InventoryItem(id, name, stock_unit_id, purchase_unit_id, category_id, purchase_to_stock_factor, family_id, description)`. Production adds stock tracking fields, cost, supplier, and CHECK constraints.

**New fields explained:**
| Field | Purpose |
|-------|---------|
| min_stock_quantity | Alert when stock falls below this level |
| current_stock_quantity | Tracks current stock (updated by deductions and purchases) |
| cost_per_purchase_unit | Last known price per purchase unit (for recipe costing) |
| supplier_name | Primary supplier reference (simple text for v1) |

---

### recipe

A recipe belonging to the restaurant.

```sql
CREATE TABLE recipe (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    category_id   UUID NOT NULL REFERENCES category_recipe(id),
    description   TEXT,
    steps         JSONB,                         -- ["Step 1...", "Step 2...", ...]
    servings      INTEGER DEFAULT 1,             -- NEW: portions per recipe execution
    prep_time_min INTEGER,                       -- NEW: preparation time in minutes
    cook_time_min INTEGER,                       -- NEW: cooking time in minutes
    image_url     TEXT,                          -- NEW: recipe photo
    is_active     BOOLEAN NOT NULL DEFAULT TRUE, -- NEW: can be deactivated without deleting
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by    UUID REFERENCES auth.users(id),
    updated_by    UUID REFERENCES auth.users(id),
    deleted_at    TIMESTAMPTZ,

    UNIQUE(tenant_id, name) WHERE deleted_at IS NULL
);
```

**MVP equivalent:** `Recipe(id, name, category_id, description, steps, ingredients)`. Production separates ingredients into own table and adds servings, time, image, and active flag.

---

### recipe_ingredient

An ingredient within a recipe. Separate table (not embedded) with full FK relationships.

```sql
CREATE TABLE recipe_ingredient (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    recipe_id           UUID NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,            -- ingredient display name
    quantity            DOUBLE PRECISION NOT NULL,
    unit_id             UUID NOT NULL REFERENCES recipe_unit(id),
    inventory_item_id   UUID REFERENCES inventory_item(id), -- FK link (not name-based)
    sort_order          INTEGER NOT NULL DEFAULT 0,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK(quantity > 0),
    UNIQUE(recipe_id, name) WHERE inventory_item_id IS NOT NULL
);
```

**MVP equivalent:** `Ingredient(name, quantity, unit_id, inventory_item_id)` embedded in Recipe.ingredients list. Production uses a proper junction table with FK to `inventory_item`.

**Key change:** `inventory_item_id` is now a proper FK reference (UUID) instead of name-based resolution. The AI alignment agent sets this FK during the Alineamiento phase.

---

### recipe_unit_conversion

Context-sensitive conversion between recipe units and inventory units. Handles cases like "1 cucharada = 15 ml" or "1 tortilla = 50 g (for this specific item)".

```sql
CREATE TABLE recipe_unit_conversion (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    recipe_unit_id      UUID NOT NULL REFERENCES recipe_unit(id),
    family_id           UUID REFERENCES family_inventory(id),     -- optional context
    inventory_item_id   UUID REFERENCES inventory_item(id),       -- optional context
    quantity            DOUBLE PRECISION NOT NULL,                 -- how much of base unit
    base_unit_id        UUID NOT NULL REFERENCES inventory_unit(id),
    source              TEXT NOT NULL DEFAULT 'manual',            -- manual, ai, standard
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by          UUID REFERENCES auth.users(id),

    CHECK(quantity > 0),
    UNIQUE(tenant_id, recipe_unit_id, family_id, inventory_item_id)
);
```

**MVP equivalent:** `RecipeUnitConversionRegistry` with composite key `(recipe_unit_id, family_id, inventory_item_id)`. Same logic, production uses UUIDs and proper FKs.

**Lookup priority (most specific wins):**
1. (recipe_unit, family, item) — item-specific
2. (recipe_unit, family, NULL) — family-level default
3. (recipe_unit, NULL, item) — item-specific, no family
4. (recipe_unit, NULL, NULL) — global default

---

## Operational Entities

These entities support the Manual Operativo phase and daily operations.

### classification

Structured classification data generated by the AI during onboarding.

```sql
CREATE TABLE classification (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    restaurant_type       TEXT NOT NULL,          -- Casual, Rapida, Gourmet, etc.
    description           TEXT NOT NULL,          -- AI-generated restaurant description
    key_characteristics   JSONB,                  -- ["family-owned", "Mexican cuisine", ...]
    cuisine_types         JSONB,                  -- ["Mexican", "International"]
    service_style         TEXT,                    -- table-service, counter, delivery, mixed
    confirmed_by_operator BOOLEAN NOT NULL DEFAULT FALSE,
    confirmed_at          TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(tenant_id)
);
```

**MVP equivalent:** JSON blob in `classification` table (`id INTEGER, data TEXT`). Production uses structured columns.

---

### standardization_progress

Tracks overall standardization progress per section. Powers the KPI dashboard.

```sql
CREATE TABLE standardization_progress (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    section           TEXT NOT NULL,              -- configuracion, alineamiento, estructura, normalizacion
    status            TEXT NOT NULL DEFAULT 'not_started', -- not_started, in_progress, completed
    total_items       INTEGER NOT NULL DEFAULT 0,
    completed_items   INTEGER NOT NULL DEFAULT 0,
    completion_pct    DOUBLE PRECISION GENERATED ALWAYS AS (
                          CASE WHEN total_items > 0
                          THEN (completed_items::float / total_items * 100)
                          ELSE 0 END
                      ) STORED,
    started_at        TIMESTAMPTZ,
    completed_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(tenant_id, section)
);
```

**MVP equivalent:** `compute_readiness_report()` function computed on the fly. Production persists progress for dashboard performance.

---

### deduction_log

Historical record of inventory deductions (when recipes are executed). Enables operational insights in the Manual Operativo.

```sql
CREATE TABLE deduction_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    recipe_id           UUID NOT NULL REFERENCES recipe(id),
    inventory_item_id   UUID NOT NULL REFERENCES inventory_item(id),
    quantity_deducted   DOUBLE PRECISION NOT NULL,
    unit_id             UUID NOT NULL REFERENCES inventory_unit(id),
    servings            INTEGER NOT NULL DEFAULT 1,
    deducted_by         UUID REFERENCES auth.users(id),
    deducted_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK(quantity_deducted > 0)
);
```

**MVP equivalent:** Did not exist. Deduction was computed but not logged.

---

## AI & Session Entities

### conversation

Tracks AI conversations per section per tenant. Each standardization section has its own conversation.

```sql
CREATE TABLE conversation (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    section       TEXT NOT NULL,              -- bienvenida, clasificacion, configuracion, etc.
    agent_type    TEXT NOT NULL,              -- welcome_agent, classification_agent, etc.
    status        TEXT NOT NULL DEFAULT 'active', -- active, completed, archived
    metadata      JSONB,                     -- section-specific state
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(tenant_id, section) WHERE status = 'active'
);
```

---

### conversation_message

Individual messages within a conversation.

```sql
CREATE TABLE conversation_message (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id   UUID NOT NULL REFERENCES conversation(id) ON DELETE CASCADE,
    role              TEXT NOT NULL,          -- user, assistant, system, tool
    content           TEXT NOT NULL,
    tool_calls        JSONB,                 -- tool call metadata (if role=assistant)
    tool_results      JSONB,                 -- tool results (if role=tool)
    token_count       INTEGER,               -- for monitoring/budgeting
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**MVP equivalent:** `ConversationMemory` (in-memory list) + `agent_state` table (JSON blob). Production persists every message for auditability and context recovery.

---

### agent_state

Persisted agent state for resuming standardization across browser sessions.

```sql
CREATE TABLE agent_state (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    agent_type    TEXT NOT NULL,              -- structuring_agent, alignment_agent, etc.
    state_data    JSONB NOT NULL,             -- agent-specific state (proposals, gaps, phase, etc.)
    version       INTEGER NOT NULL DEFAULT 1, -- state schema version for migrations
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(tenant_id, agent_type)
);
```

**MVP equivalent:** `agent_state(session_id TEXT, data TEXT)`. Production uses JSONB with versioning.

---

## Enumerations (Fixed Values)

These values are enforced at the application level (not separate tables). Defined as TypeScript/Python enums.

### Restaurant Types
```
Casual | Rapida | Gourmet | Cafeteria | Cafe
```

### Inventory Categories
```
perishable | non_perishable
```

### Tenant Member Roles
```
owner | admin | chef | staff
```

### Conversation Sections
```
bienvenida | clasificacion | configuracion | alineamiento | estructura | normalizacion | manual_operativo
```

### Standardization Section Status
```
not_started | in_progress | completed
```

### Conversation Message Roles
```
user | assistant | system | tool
```

**MVP equivalent:** `RestaurantType` and `InventoryCategory` were separate tables with integer IDs. `ALLOWED_USER_ROLES` was a frozenset. Production uses string enums for simplicity and readability.

---

## Indexes & Performance

```sql
-- Tenant-scoped lookups (most frequent queries)
CREATE INDEX idx_restaurant_tenant ON restaurant(tenant_id);
CREATE INDEX idx_recipe_tenant ON recipe(tenant_id, category_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_inventory_item_tenant ON inventory_item(tenant_id, family_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_recipe_ingredient_recipe ON recipe_ingredient(recipe_id);
CREATE INDEX idx_recipe_ingredient_item ON recipe_ingredient(inventory_item_id);

-- Unit lookups
CREATE INDEX idx_inventory_unit_tenant ON inventory_unit(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_recipe_unit_tenant ON recipe_unit(tenant_id) WHERE deleted_at IS NULL;

-- Configuration lookups
CREATE INDEX idx_category_recipe_tenant ON category_recipe(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_family_inventory_tenant ON family_inventory(tenant_id) WHERE deleted_at IS NULL;

-- Conversation queries
CREATE INDEX idx_conversation_tenant ON conversation(tenant_id, section);
CREATE INDEX idx_conversation_message_conv ON conversation_message(conversation_id, created_at);

-- Operational queries
CREATE INDEX idx_deduction_log_tenant ON deduction_log(tenant_id, deducted_at);
CREATE INDEX idx_deduction_log_recipe ON deduction_log(recipe_id);
CREATE INDEX idx_deduction_log_item ON deduction_log(inventory_item_id);

-- Progress dashboard
CREATE INDEX idx_standardization_progress_tenant ON standardization_progress(tenant_id);

-- Tenant membership
CREATE INDEX idx_tenant_member_user ON tenant_member(user_id) WHERE is_active = TRUE;
CREATE INDEX idx_tenant_member_tenant ON tenant_member(tenant_id) WHERE is_active = TRUE;
```

---

## Row-Level Security (RLS)

Every tenant-scoped table gets the same base RLS policy pattern:

```sql
-- Enable RLS
ALTER TABLE recipe ENABLE ROW LEVEL SECURITY;

-- SELECT: user can read rows from tenants they belong to
CREATE POLICY "tenant_read" ON recipe FOR SELECT USING (
    tenant_id IN (
        SELECT tenant_id FROM tenant_member
        WHERE user_id = auth.uid() AND is_active = TRUE
    )
);

-- INSERT: user can insert rows into tenants they belong to (with role check)
CREATE POLICY "tenant_insert" ON recipe FOR INSERT WITH CHECK (
    tenant_id IN (
        SELECT tenant_id FROM tenant_member
        WHERE user_id = auth.uid()
        AND is_active = TRUE
        AND role IN ('owner', 'admin', 'chef')
    )
);

-- UPDATE: same as insert
CREATE POLICY "tenant_update" ON recipe FOR UPDATE USING (
    tenant_id IN (
        SELECT tenant_id FROM tenant_member
        WHERE user_id = auth.uid()
        AND is_active = TRUE
        AND role IN ('owner', 'admin', 'chef')
    )
);

-- DELETE: owner and admin only
CREATE POLICY "tenant_delete" ON recipe FOR DELETE USING (
    tenant_id IN (
        SELECT tenant_id FROM tenant_member
        WHERE user_id = auth.uid()
        AND is_active = TRUE
        AND role IN ('owner', 'admin')
    )
);
```

**Tables requiring RLS:** tenant_member, restaurant, recipe_unit, inventory_unit, category_recipe, family_inventory, inventory_item, recipe, recipe_ingredient, recipe_unit_conversion, classification, standardization_progress, deduction_log, conversation, conversation_message, agent_state.

---

## Migration Strategy

### Supabase migrations

All schema changes managed via Supabase CLI migrations:

```bash
supabase migration new create_initial_schema
supabase db push
```

Migration files stored in `supabase/migrations/` (ordered by timestamp).

### Seed data

Standard units, default categories, and template data seeded per restaurant type:

```
supabase/seed.sql
├── Standard recipe units (g, kg, ml, L, pza)
├── Standard inventory units (g, kg, ml, L, pza) with equivalence chains
├── Default inventory categories (perishable, non_perishable)
└── Template data per restaurant type (category_recipe, family_inventory)
```

Templates are applied when a restaurant completes classification — the system creates tenant-specific copies of the template data.

---

## Entity Count Summary

| Layer | Table | MVP Equivalent |
|-------|-------|---------------|
| **Auth & Tenancy** | tenant | (none) |
| | profile | user |
| | tenant_member | UserRegistry |
| **Configuration** | restaurant | Restaurant |
| | recipe_unit | RecipeUnit |
| | inventory_unit | InventoryUnit |
| | category_recipe | CategoryRecipe |
| | family_inventory | FamilyInventory |
| **Recipe & Inventory** | recipe | Recipe |
| | recipe_ingredient | Ingredient (embedded) |
| | inventory_item | InventoryItem |
| **Normalization** | recipe_unit_conversion | RecipeUnitConversionRegistry |
| **Operations** | classification | classification (JSON blob) |
| | standardization_progress | compute_readiness_report() |
| | deduction_log | (none) |
| **AI & Sessions** | conversation | ConversationMemory |
| | conversation_message | (in-memory list) |
| | agent_state | agent_state (JSON blob) |
| **Total** | **17 tables** | **13 tables/entities** |

---

## Open Questions

### 1. Supplier as entity vs. text field?
**Current design:** `supplier_name` is a TEXT field on `inventory_item`.
**Alternative:** Separate `supplier` table with contact info, linked to items via junction table.
**Recommendation:** Start with TEXT field. Create supplier entity when multi-supplier tracking is needed.

### 2. Recipe versioning?
**Current design:** Recipes are mutable. Edits overwrite the previous version.
**Alternative:** Version history table (`recipe_version`) for tracking changes over time.
**Recommendation:** Defer to post-launch. Soft delete + audit fields (updated_by, updated_at) cover basic history.

### 3. Multi-location support?
**Current design:** One restaurant per tenant.
**Alternative:** One tenant, multiple restaurants (each with its own recipes/inventory).
**Recommendation:** v1 is one-to-one. Multi-location is a v2 feature requiring `restaurant_id` on all tenant-scoped tables.

### 4. Inventory transactions (stock in/out)?
**Current design:** `current_stock_quantity` on `inventory_item` + `deduction_log` for recipe deductions.
**Alternative:** Full inventory transaction ledger (`stock_movement` table: type=purchase|deduction|adjustment|waste).
**Recommendation:** Start with deduction_log only. Expand to full transaction ledger when purchase tracking is implemented.

### 5. Recipe costing rollup?
**Current design:** `cost_per_purchase_unit` on individual items. No recipe-level cost calculation.
**Alternative:** Computed `recipe_cost` view that sums ingredient costs.
**Recommendation:** Implement as a PostgreSQL view or computed at API level. No need for a stored column.

### 6. Taxonomy persistence?
**MVP:** Taxonomies (IngredientTaxonomy, RecipeTaxonomy, InventoryTaxonomy) were in-memory only.
**Production:** Do we need persisted taxonomy tables, or is the flat structure (categories + families) sufficient?
**Recommendation:** Flat structure is sufficient for v1. Taxonomy tables add complexity without clear user value yet.

### 7. File upload storage?
**Need:** Operators upload PDFs, Excel files, and images during standardization.
**Options:** Supabase Storage (S3-compatible), direct S3, or process-and-discard.
**Recommendation:** Supabase Storage for uploaded files. Store reference URL in relevant entity. Process content via AI on upload.
