# Zenet — Production Software

Cognitive operating system for restaurant back-of-house operations. Standardizes processes, automates workflows, and interprets operational data with AI guidance.

## Overview

Zenet is a SaaS platform that helps independent restaurants (1-5 locations) transform operational chaos into intelligent control. Rather than another tool, Zenet is a system that guides operators through standardizing their recipes, inventory, and processes — then generates a living operational manual that adapts in real-time.

### The Problem We Solve

Medium-sized independent restaurants operate with:
- Manual, repetitive processes consuming 70% of manager time
- No operational standardization (each person does things their own way)
- Inventory that never adds up
- Decisions made by intuition, not data
- Inability to scale without multiplying chaos

Existing tools (POS systems, inventory apps, Excel) don't solve this because they're isolated tools, not systems. **Zenet is infrastructure for operational intelligence.**

### How It Works

Zenet guides restaurants through three phases:

1. **Onboarding** — Set up account and restaurant profile with AI assistance
2. **Standardization** — Structure recipes, inventory units, families, and categories through a 6-section guided experience
3. **Manual Operativo** — See the living result: KPIs, standardization dimensions, improvement areas, and AI insights

Every step is guided by an AI assistant that understands the restaurant's context and helps translate messy real-world knowledge into clean operational data.

---

## Key Features (v1.0)

### Onboarding Phase
- Account creation with email/password via Supabase Auth
- Restaurant profile setup (name, type, address, contact info)
- AI assistant introduction and guided classification

### Standardization Phase (6 Sections)
- **Clasificacion** — Restaurant type, profile, and operational style
- **Configuracion** — Recipe categories, inventory families, recipe units, inventory units
- **Alineamiento** — Recipe-by-recipe entry and ingredient-to-inventory mapping
- **Estructura** — Inventory enrichment (stock/purchase units, conversion factors, families)
- **Normalizacion** — Detect and resolve unit mismatches between recipe and inventory units via AI agent

### Manual Operativo Phase
- KPI dashboard (standardization scores and progress)
- Standardization dimensions breakdown
- AI-generated improvement suggestions
- Real-time updates as data changes

### AI Assistant
- Persistent sidebar available across all phases
- File upload and parsing (recipes, inventories)
- Natural language conversation
- Contextual suggestions and gap detection
- Interpretation mode for operational insights

---

## Technology Stack

### Frontend
- **Framework:** Next.js 15+ (App Router)
- **Language:** TypeScript
- **UI Components:** shadcn/ui + Radix UI
- **Styling:** Tailwind CSS
- **State Management:** Zustand
- **Data Fetching:** TanStack Query
- **Forms:** react-hook-form + zod

### Backend
- **Framework:** FastAPI (Python 3.13)
- **Validation:** Pydantic
- **Rate Limiting:** slowapi
- **Environment:** python-dotenv

### Database & Services
- **Database:** Supabase (managed PostgreSQL)
- **Authentication:** Supabase Auth (JWT)
- **Row-Level Security:** Enabled for multi-tenancy
- **AI:** Anthropic Claude API
- **AI Monitoring:** Langfuse
- **Deployment (Frontend):** Vercel
- **Deployment (Backend):** Railway

### Testing
- **Unit Tests:** pytest (backend), vitest (frontend)
- **E2E Tests:** Playwright
- **Accessibility:** axe-core

---

## Project Structure

```
zenet/
│
├── CLAUDE.md                          # Claude Code instructions
├── README.md                          # This file
├── .env.example                       # Environment variables template
├── .gitignore
│
├── docs/                              # All project documentation
│   ├── business-context.md            # Business context & strategy
│   ├── core-user-experience.md        # UX flows & design decisions
│   ├── production-strategy.md         # Technical strategy
│   ├── database-schema.md             # Database schema docs
│   └── api-design.md                  # API design decisions
│
├── frontend/                          # Next.js application
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   ├── components.json                # shadcn/ui config
│   │
│   ├── public/                        # Static assets
│   │   ├── images/
│   │   └── fonts/
│   │
│   ├── src/
│   │   ├── app/                       # Next.js App Router
│   │   │   ├── layout.tsx             # Root layout
│   │   │   ├── page.tsx               # Landing page
│   │   │   ├── (auth)/                # Auth route group
│   │   │   │   ├── login/page.tsx
│   │   │   │   ├── register/page.tsx
│   │   │   │   └── layout.tsx         # Auth layout (centered card)
│   │   │   └── (dashboard)/           # Authenticated route group
│   │   │       ├── layout.tsx         # Dashboard layout (sidebar + AI)
│   │   │       ├── page.tsx           # Dashboard home
│   │   │       ├── onboarding/page.tsx
│   │   │       ├── standardization/
│   │   │       │   ├── page.tsx       # Standardization hub
│   │   │       │   ├── clasificacion/page.tsx
│   │   │       │   ├── configuracion/page.tsx
│   │   │       │   ├── alineamiento/page.tsx
│   │   │       │   ├── estructura/page.tsx
│   │   │       │   └── normalizacion/page.tsx
│   │   │       ├── manual-operativo/
│   │   │       │   ├── page.tsx       # KPI dashboard
│   │   │       │   ├── dimensions/page.tsx
│   │   │       │   └── suggestions/page.tsx
│   │   │       └── settings/
│   │   │           ├── page.tsx
│   │   │           ├── team/page.tsx
│   │   │           └── billing/page.tsx
│   │   │
│   │   ├── components/                # Reusable UI components
│   │   │   ├── ui/                    # shadcn/ui (auto-generated)
│   │   │   ├── layout/               # Sidebar, header, AI sidebar
│   │   │   ├── chat/                  # AI assistant components
│   │   │   ├── standardization/       # Section-specific components
│   │   │   └── manual-operativo/      # Manual operativo components
│   │   │
│   │   ├── hooks/                     # Custom React hooks
│   │   │   ├── use-auth.ts
│   │   │   ├── use-restaurant.ts
│   │   │   ├── use-chat.ts
│   │   │   └── use-standardization.ts
│   │   │
│   │   ├── lib/                       # Utilities and configuration
│   │   │   ├── supabase/
│   │   │   │   ├── client.ts          # Browser Supabase client
│   │   │   │   ├── server.ts          # Server-side Supabase client
│   │   │   │   └── middleware.ts      # Auth middleware
│   │   │   ├── api.ts                 # Backend API client
│   │   │   ├── utils.ts
│   │   │   └── constants.ts
│   │   │
│   │   ├── stores/                    # Zustand stores
│   │   │   ├── auth-store.ts
│   │   │   ├── restaurant-store.ts
│   │   │   └── chat-store.ts
│   │   │
│   │   └── types/                     # TypeScript type definitions
│   │       ├── restaurant.ts
│   │       ├── recipe.ts
│   │       ├── inventory.ts
│   │       └── api.ts
│   │
│   └── tests/                         # Frontend tests
│       ├── components/
│       └── e2e/                        # Playwright tests
│
├── backend/                           # FastAPI application
│   ├── pyproject.toml                 # Python project config (uv)
│   ├── .python-version                # Python 3.13
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── config.py                  # Settings (env vars, constants)
│   │   │
│   │   ├── api/                       # API layer
│   │   │   ├── __init__.py
│   │   │   ├── deps.py               # Shared dependencies (get_db, get_user)
│   │   │   └── v1/                    # API version 1
│   │   │       ├── __init__.py
│   │   │       ├── router.py          # Aggregates all v1 routers
│   │   │       ├── auth.py
│   │   │       ├── restaurants.py
│   │   │       ├── standardization.py
│   │   │       ├── manual_operativo.py
│   │   │       └── ai.py
│   │   │
│   │   ├── models/                    # Database models
│   │   │   ├── restaurant.py
│   │   │   ├── recipe.py
│   │   │   ├── inventory.py
│   │   │   ├── user.py
│   │   │   └── unit.py
│   │   │
│   │   ├── schemas/                   # Pydantic request/response schemas
│   │   │   ├── restaurant.py
│   │   │   ├── recipe.py
│   │   │   ├── inventory.py
│   │   │   ├── auth.py
│   │   │   └── ai.py
│   │   │
│   │   ├── services/                  # Business logic
│   │   │   ├── restaurant_service.py
│   │   │   ├── standardization_service.py
│   │   │   ├── manual_operativo_service.py
│   │   │   └── validation_service.py
│   │   │
│   │   ├── agents/                    # AI agent implementations
│   │   │   ├── base_agent.py
│   │   │   ├── onboarding_agent.py
│   │   │   ├── classification_agent.py
│   │   │   ├── configuration_agent.py
│   │   │   ├── alignment_agent.py
│   │   │   ├── structuring_agent.py
│   │   │   ├── normalization_agent.py
│   │   │   └── interpretation_agent.py
│   │   │
│   │   ├── core/                      # Core domain logic
│   │   │   ├── normalization.py       # Unit conversion logic
│   │   │   ├── readiness.py           # KPI computation
│   │   │   └── taxonomy.py            # Ingredient/inventory hierarchies
│   │   │
│   │   └── middleware/                # Custom middleware
│   │       ├── auth.py                # JWT validation
│   │       └── rate_limit.py          # Rate limiting
│   │
│   ├── scripts/                       # Utility scripts
│   │   ├── seed_data.py
│   │   └── reset_db.py
│   │
│   └── tests/                         # Backend tests
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_restaurants.py
│       ├── test_standardization.py
│       ├── test_agents.py
│       └── test_manual_operativo.py
│
└── supabase/                          # Supabase configuration
    ├── migrations/                    # SQL migrations
    │   └── 001_initial_schema.sql
    ├── seed.sql                       # Seed data
    └── config.toml                    # Supabase local config
```

---

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.13+
- PostgreSQL 14+ (or Supabase account)
- Anthropic API key
- (Optional) OpenAI API key

### Environment Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/zenet-production.git
   cd zenet-production
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env.local
   ```
   Fill in:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `ANTHROPIC_API_KEY`
   - `DATABASE_URL` (PostgreSQL)

3. **Install dependencies**
   ```bash
   # Frontend
   cd frontend && npm install

   # Backend
   cd ../backend && uv sync
   ```

4. **Start local development**
   ```bash
   # Frontend (from frontend/)
   npm run dev

   # Backend (from backend/)
   uv run python app/main.py
   ```
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API docs: http://localhost:8000/docs

---

## Core Concepts

### The Three Phases

| Phase | Duration | Goal | Output |
|---|---|---|---|
| **Onboarding** | 5-10 min | Set up account and restaurant profile | Account created, context established |
| **Standardization** | 2-4 hours | Structure recipes, inventory, units, families | Complete operational foundation |
| **Manual Operativo** | Ongoing | Review KPIs, track standardization, apply insights | Living operational dashboard |

### Restaurant Standardization

Zenet structures a restaurant through 6 progressive sections:

1. **Clasificacion** — Restaurant type, profile, and operational style
2. **Configuracion** — Recipe categories, inventory families, recipe units, inventory units
3. **Alineamiento** — Recipes entered recipe-by-recipe, ingredients mapped to inventory items
4. **Estructura** — Inventory items enriched with stock/purchase units, conversion factors, families
5. **Normalizacion** — Unit mismatches between recipes and inventory detected and resolved via AI agent
6. **Review** — Operator confirms each section's output before advancing

Each section builds on the previous one, progressively creating a complete operational model.

### The AI Assistant

The AI assistant (Claude-based agent) is always available and context-aware. It:
- Guides operators through standardization
- Processes file uploads (recipes, inventories)
- Suggests data and resolves ambiguities
- Interprets KPIs and operational insights
- Never makes changes without confirmation

---

## API Overview

### Key Endpoints (v1.0)

**Authentication**
- `POST /api/v1/auth/register` — Sign up
- `POST /api/v1/auth/login` — Login
- `POST /api/v1/auth/refresh` — Refresh token

**Restaurant**
- `POST /api/v1/restaurants` — Create restaurant
- `GET /api/v1/restaurants/{id}` — Get restaurant profile
- `PATCH /api/v1/restaurants/{id}` — Update restaurant

**Standardization Sections**
- `POST /api/v1/standardization/{section}` — Submit section data
- `GET /api/v1/standardization/{section}` — Retrieve section data
- `PATCH /api/v1/standardization/{section}` — Update section

**Manual Operativo**
- `GET /api/v1/manual-operativo/dashboard` — KPI dashboard
- `GET /api/v1/manual-operativo/dimensions` — Standardization dimensions
- `GET /api/v1/manual-operativo/suggestions` — AI suggestions

**AI Assistant**
- `POST /api/v1/ai/chat` — Send message to assistant
- `POST /api/v1/ai/upload` — Upload file for processing
- `GET /api/v1/ai/history` — Retrieve conversation history

Full API documentation available at `/api/docs` (Swagger/OpenAPI).

---

## Database Schema (Overview)

17 tables across 6 layers. All IDs are UUIDs. All tenant-scoped tables include `tenant_id`, `created_at`, `updated_at`, and soft delete (`deleted_at`).

### Auth & Tenancy
- **tenant** — Top-level business entity (one per restaurant business)
- **profile** — Extends Supabase Auth users with app-specific data
- **tenant_member** — Junction: user-to-tenant with roles (owner, admin, chef, staff)

### Configuration
- **restaurant** — Restaurant profile (name, type, address, contact, operating hours)
- **recipe_unit** — Units for recipe instructions (g, kg, cucharada, porcion)
- **inventory_unit** — Units for inventory tracking (kg, caja, bolsa) with self-referential equivalence chains
- **category_recipe** — Recipe categories (Entradas, Platos Fuertes, Bebidas)
- **family_inventory** — Inventory grouping (Carnes, Lacteos, Verduras)

### Recipe & Inventory
- **recipe** — Recipes with category, steps, servings, prep/cook time
- **recipe_ingredient** — Ingredients per recipe with FK to inventory_item (not name-based)
- **inventory_item** — Items with dual units (stock + purchase), conversion factor, stock levels, cost

### Normalization
- **recipe_unit_conversion** — Context-sensitive conversion between recipe and inventory units

### Operations
- **classification** — Structured restaurant classification (not JSON blob)
- **standardization_progress** — Per-section completion tracking for KPI dashboard
- **deduction_log** — Historical record of inventory deductions

### AI & Sessions
- **conversation** / **conversation_message** — Persisted chat history per section
- **agent_state** — Agent state with JSONB and schema versioning

See `/docs/data-model-overview.md` for complete schema, relationships, and RLS policies.

---

## Multi-Tenancy

Zenet uses a tenant-based multi-tenancy model. One tenant = one restaurant business (v1: one restaurant per tenant). Users can belong to multiple tenants (e.g., a consultant managing several restaurants).

**Data Isolation:**
- PostgreSQL Row-Level Security (RLS) enforces tenant-level isolation
- JWT contains `user_id`; RLS policies join through `tenant_member` to determine access
- All tenant-scoped tables include `tenant_id` with RLS policies for SELECT, INSERT, UPDATE, DELETE

**User Roles (via `tenant_member`):**
- **Owner** — Full access (billing, team management, all sections, delete tenant)
- **Admin** — Everything except billing
- **Chef** — Recipes, inventory, manual operativo
- **Staff** — Read-only access to manual operativo and KPIs

---

## Deployment

### Development
```bash
docker-compose up  # Starts PostgreSQL, frontend, backend
```

### Staging / Production
- **Frontend:** Deployed to Vercel (automatic on main branch push)
- **Backend:** Deployed to Railway (automatic on main branch push)
- **Database:** Supabase (managed PostgreSQL)

See `CONTRIBUTING.md` for deployment procedures.

---

## Testing

```bash
# Backend tests
cd backend && uv run pytest

# Frontend tests
cd frontend && npm run test

# E2E tests
cd frontend && npm run test:e2e
```

---

## Roadmap

**Timeline:** April 2026 — October 2026 (7 months)

| Month | Phase | Key Deliverables |
|-------|-------|-----------------|
| April | Foundation | Supabase schema, API scaffold, frontend scaffold, deployment pipeline |
| May | Onboarding | Auth, Bienvenida, AI assistant infrastructure, profile, Clasificacion |
| June | Configuracion | Agent, recipe categories, inventory families, recipe/inventory units, multi-input |
| July | Alineamiento | Recipe agent, recipe-by-recipe input, ingredient-to-inventory linking |
| August | Estructura | Inventory agent, structuring, perecedero/no perecedero flow |
| September | Normalizacion | Normalization agent, per-recipe mismatch table, chat-based resolution |
| October | Manual Operativo | KPIs, standardization dimensions, improvement areas, AI chat, admin panel |

**37 features** across 7 months. See `/docs/feature-roadmap.md` for detailed feature breakdown, dependencies, and success criteria.

### Future (v2.0+)
- [ ] Multi-location support
- [ ] Mobile app
- [ ] POS integrations
- [ ] Forecasting module
- [ ] Supply chain optimization
- [ ] Advanced analytics

---

## Contributing

See `CONTRIBUTING.md` for guidelines on:
- Code style and standards
- Commit message format
- Pull request process
- Testing requirements

---

## Security

- JWT authentication via Supabase
- Row-Level Security (RLS) for data isolation
- Pydantic validation on all inputs
- Rate limiting via slowapi
- CORS configured for production domains
- Secrets managed via environment variables (never committed)

See `/docs/security.md` for detailed security information.

---

## Documentation

- **Business Context:** `/docs/business-context.md` — Problem, solution, market, value proposition, validation status
- **Core User Experience:** `/docs/core-user-experience.md` — Three-phase UX flow, personas, AI assistant behavior
- **Feature Roadmap:** `/docs/feature-roadmap.md` — 37 features across 7 months, dependencies, success criteria
- **Data Model Overview:** `/docs/data-model-overview.md` — 17 tables, relationships, RLS policies, migration strategy
- **API Design:** `/docs/api-design.md` — Endpoint conventions, versioning, error handling
- **API Reference:** http://localhost:8000/docs (interactive Swagger UI)

---

## License

MIT

---

## Support

For questions or issues:
1. Check existing GitHub issues
2. Create a new GitHub issue with description and steps to reproduce
3. Contact the team at [support email]

---

## Status

**Current Phase:** v1.0 Development
**Last Updated:** April 6, 2026
**Maintained by:** Zenet Team

---

*For detailed business context, strategy, and UX decisions, see the Business Context document in `/docs`.*
