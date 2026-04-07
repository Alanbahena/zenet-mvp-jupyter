# CLAUDE.md — Zenet Production Software

## Project Overview

**Zenet** is a cognitive operating system for restaurant back-of-house operations. It is a multi-tenant SaaS platform that guides restaurant operators through standardizing their recipes, inventory, and processes — then generates a living operational manual (Manual Operativo) with KPIs and AI insights.

**This is NOT the MVP.** This is the production software built with Next.js + FastAPI + Supabase. The MVP (Gradio + SQLite) lives in a separate repository and serves as the prototype reference.

---

## Environment

- **Frontend:** Next.js 15+ (App Router), TypeScript, React 19
- **Backend:** FastAPI, Python 3.13
- **Database:** Supabase (managed PostgreSQL)
- **Auth:** Supabase Auth (email/password, JWT)
- **AI:** Anthropic Claude API (Sonnet 4.6 default, Opus 4.6 for complex tasks)
- **AI Monitoring:** Langfuse
- **Package managers:** npm (frontend), uv (backend) — never use pip
- **Deployment:** Vercel (frontend), Railway (backend)

---

## Key Commands

```bash
# ── Frontend (from frontend/) ──
npm install                  # Install dependencies
npm run dev                  # Start dev server (http://localhost:3000)
npm run build                # Production build
npm run test                 # Run vitest
npm run test:e2e             # Run Playwright E2E tests
npm run lint                 # ESLint

# ── Backend (from backend/) ──
uv sync                      # Install dependencies
uv add <package>              # Add a new dependency
uv run uvicorn app.main:app --reload  # Start dev server (http://localhost:8000)
uv run pytest tests/          # Run all tests
uv run pytest tests/test_auth.py      # Run specific test file

# ── Supabase ──
supabase start                # Start local Supabase
supabase db push              # Push migrations to local
supabase migration new <name> # Create a new migration
supabase db reset             # Reset local DB and re-seed

# ── Full stack ──
# Terminal 1: cd frontend && npm run dev
# Terminal 2: cd backend && uv run uvicorn app.main:app --reload
# Terminal 3: supabase start (if local)
```

---

## Project Structure

```
zenet/
├── CLAUDE.md                          # This file
├── README.md
├── .env.example
│
├── docs/                              # Project documentation
│   ├── business-context.md
│   ├── core-user-experience.md
│   ├── feature-roadmap.md
│   ├── data-model-overview.md
│   └── api-design.md
│
├── frontend/                          # Next.js application
│   ├── src/app/                       # App Router pages
│   │   ├── (auth)/                    # Login, register (public)
│   │   └── (dashboard)/              # Authenticated routes
│   │       ├── onboarding/
│   │       ├── standardization/      # 6 sections
│   │       ├── manual-operativo/
│   │       └── settings/
│   ├── src/components/               # React components
│   │   ├── ui/                       # shadcn/ui (auto-generated, do not edit)
│   │   ├── layout/                   # Sidebar, header, AI sidebar
│   │   ├── chat/                     # AI assistant components
│   │   ├── standardization/          # Section-specific components
│   │   └── manual-operativo/
│   ├── src/hooks/                    # Custom React hooks
│   ├── src/lib/                      # Utilities, Supabase clients, API client
│   ├── src/stores/                   # Zustand stores
│   └── src/types/                    # TypeScript type definitions
│
├── backend/                          # FastAPI application
│   ├── app/
│   │   ├── main.py                   # FastAPI entry point
│   │   ├── config.py                 # Settings
│   │   ├── api/v1/                   # API routes (versioned)
│   │   ├── models/                   # Database models (Pydantic)
│   │   ├── schemas/                  # Request/response schemas
│   │   ├── services/                 # Business logic
│   │   ├── agents/                   # AI agent implementations
│   │   ├── core/                     # Domain logic (normalization, readiness, taxonomy)
│   │   └── middleware/               # Auth, rate limiting
│   └── tests/
│
└── supabase/                         # Supabase configuration
    ├── migrations/                   # SQL migrations (ordered by timestamp)
    └── seed.sql                      # Seed data
```

---

## Architecture & Conventions

### Multi-Tenancy

- Every tenant-scoped table has a `tenant_id UUID` column
- Row-Level Security (RLS) enforces data isolation — users only see data for tenants they belong to
- RLS policies join through `tenant_member` using `auth.uid()` from JWT
- One tenant = one restaurant (v1). Multi-location is a v2 feature
- User roles: `owner`, `admin`, `chef`, `staff` (defined in `tenant_member.role`)

### IDs

- All entity IDs are **UUIDs** (`gen_random_uuid()` in PostgreSQL)
- Never use sequential integers for IDs
- Supabase Auth user IDs are also UUIDs

### Timestamps & Audit

- Every table has `created_at TIMESTAMPTZ` and `updated_at TIMESTAMPTZ`
- Tenant-scoped tables have `created_by UUID` and `updated_by UUID` referencing `auth.users(id)`
- Soft deletes via `deleted_at TIMESTAMPTZ` — never hard delete user data
- Unique constraints use `WHERE deleted_at IS NULL` to allow re-creation after soft delete

### Frontend Conventions

- **Components:** Use shadcn/ui + Radix UI. Do not install other component libraries
- **Styling:** Tailwind CSS only. No CSS modules, no styled-components
- **State:** Zustand for client state. TanStack Query for server state
- **Forms:** react-hook-form + zod for validation
- **Routing:** Next.js App Router. Use route groups `(auth)` and `(dashboard)`
- **API calls:** All backend calls go through `src/lib/api.ts` client
- **Types:** Define in `src/types/`. Keep in sync with backend Pydantic schemas

### Backend Conventions

- **Validation:** Pydantic for all request/response schemas. Never trust raw input
- **No ORM:** Use Supabase client library for queries, not SQLAlchemy
- **API versioning:** All routes under `/api/v1/`. Never break v1 once released
- **Error responses:** Use standard HTTP status codes. Return `{"detail": "message"}` for errors
- **Agent pattern:** All AI agents extend `BaseAgent`. Use `create_agent()` factory — never instantiate directly
- **Prompts:** All prompts in dedicated files under `agents/`. Never hardcode prompts in route handlers

### Database Conventions

- Table names: `snake_case`, singular (`recipe`, not `recipes`)
- Column names: `snake_case`
- Foreign keys: `<entity>_id` (e.g., `tenant_id`, `recipe_id`, `family_id`)
- Enums: TEXT columns with application-level validation, not PostgreSQL ENUM types
- JSONB: Use sparingly — only for truly dynamic data (operating_hours, metadata, steps)
- Migrations: One migration per feature. Never modify existing migrations — create a new one

---

## Data Model (17 Tables)

### Auth & Tenancy
- `tenant` — Business entity (name, slug, plan)
- `profile` — Extends auth.users (full_name, avatar, phone)
- `tenant_member` — User-to-tenant with role (owner/admin/chef/staff)

### Configuration
- `restaurant` — Profile (name, type, address, contact, operating_hours)
- `recipe_unit` — Recipe measurement units (g, kg, cucharada, porcion)
- `inventory_unit` — Inventory units with self-referential equivalence chains (kg → g × 1000)
- `category_recipe` — Recipe categories (Entradas, Platos Fuertes, Bebidas)
- `family_inventory` — Inventory grouping (Carnes, Lacteos, Verduras)

### Recipe & Inventory
- `recipe` — Recipes (name, category, steps, servings, prep/cook time)
- `recipe_ingredient` — Ingredients per recipe with FK to inventory_item
- `inventory_item` — Dual-unit items (stock_unit + purchase_unit + conversion factor)

### Normalization
- `recipe_unit_conversion` — Context-sensitive recipe-to-inventory unit conversions

### Operations
- `classification` — Structured restaurant classification data
- `standardization_progress` — Per-section completion tracking
- `deduction_log` — Historical inventory deduction records

### AI & Sessions
- `conversation` + `conversation_message` — Persisted chat history per section
- `agent_state` — Agent state with JSONB and versioning

See `docs/data-model-overview.md` for full schema, relationships, and RLS policies.

---

## The Three Phases

### Phase 1: Onboarding
- Account creation (Supabase Auth)
- Bienvenida (AI welcome)
- Restaurant profile setup
- Clasificacion (AI-guided restaurant classification)

### Phase 2: Standardization (6 sections, sequential)
1. **Clasificacion** — Restaurant type and operational profile
2. **Configuracion** — Recipe categories, inventory families, recipe/inventory units
3. **Alineamiento** — Recipe-by-recipe entry, ingredient-to-inventory mapping
4. **Estructura** — Inventory enrichment (stock/purchase units, conversion factors, families)
5. **Normalizacion** — Detect and resolve unit mismatches between recipes and inventory
6. **Review** — Operator confirms each section before advancing

### Phase 3: Manual Operativo
- KPI dashboard (standardization scores)
- Standardization dimensions breakdown
- AI-identified improvement areas
- Persistent AI assistant for operational questions
- Data visualization (restaurant, recipes, inventory, normalizations)
- Admin panel

---

## AI Agents

8 agents, all extending `BaseAgent`:

| Agent | Section | Purpose |
|-------|---------|---------|
| OnboardingAgent | Bienvenida | Welcome and introduction |
| ClassificationAgent | Clasificacion | Restaurant type classification |
| ConfigurationAgent | Configuracion | Guide unit/family/category setup |
| AlignmentAgent | Alineamiento | Recipe entry and ingredient mapping |
| StructuringAgent | Estructura | Inventory enrichment |
| NormalizationAgent | Normalizacion | Unit mismatch detection and resolution |
| InterpretationAgent | Manual Operativo | Data interpretation and insights |
| ConsistencyCheckAgent | Cross-section | Validate data consistency |

**AI conventions:**
- Default model: Claude Sonnet 4.6 (`claude-sonnet-4-6`)
- Complex reasoning: Claude Opus 4.6 (`claude-opus-4-6`)
- All prompts in Spanish (user-facing) with English code comments
- Monitor all AI calls via Langfuse
- Never make changes without operator confirmation
- File uploads processed via vision models for images, text extraction for PDFs/Excel

---

## Environment Variables

API keys live in `.env` (never commit this file). Copy from `.env.example`:

```
# Supabase
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# Backend
DATABASE_URL=
ANTHROPIC_API_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=

# Optional
OPENAI_API_KEY=
```

---

## Testing

- **Backend:** pytest — unit tests per module, test files mirror app structure
- **Frontend:** vitest — component and hook tests
- **E2E:** Playwright — critical user flows (sign up → standardization → manual operativo)
- **Accessibility:** axe-core integrated in E2E tests
- Always add tests for new features. Tests should cover normal cases, edge cases, and validation failures

---

## Git Workflow

- **Branching:** GitHub Flow — `main` + `feature/*` + `bugfix/*`
- **main** is always deployable (auto-deploys to Vercel + Railway)
- Never commit directly to main — always use PRs
- Delete feature branches after merge
- Commit messages: imperative mood, concise ("Add recipe creation endpoint", not "Added...")

---

## Key Constraints

- **No ORM** — use Supabase client, not SQLAlchemy
- **No auto-commit** — never commit unless explicitly asked
- **uv over pip** — always use `uv add` / `uv sync` for Python
- **npm for frontend** — standard npm commands
- **No emojis** in code or responses unless explicitly requested
- **No over-engineering** — only build what the current task requires
- **API keys in .env only** — never hardcode credentials
- **`.env` must never be committed**
- **All user-facing text in Spanish** — code comments and variable names in English
- **shadcn/ui components are auto-generated** — do not manually edit files in `components/ui/`

---

## Reference Documents

| Document | Location | Description |
|----------|----------|-------------|
| Business Context | `docs/business-context.md` | Problem, solution, market, personas, value proposition |
| Core User Experience | `docs/core-user-experience.md` | Three-phase UX flow, AI assistant behavior, personas |
| Feature Roadmap | `docs/feature-roadmap.md` | 37 features across 7 months (Apr–Oct 2026) |
| Data Model Overview | `docs/data-model-overview.md` | 17 tables, relationships, RLS policies, migration strategy |
| API Design | `docs/api-design.md` | Endpoint conventions, versioning, error handling |
