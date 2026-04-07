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
2. **Standardization** — Structure recipes, inventory units, families, and categories through a 5-section guided experience
3. **Manual Operativo** — See the living result: KPIs, standardization dimensions, improvement areas, and AI insights

Every step is guided by an AI assistant that understands the restaurant's context and helps translate messy real-world knowledge into clean operational data.

---

## Key Features (v1.0)

### Onboarding Phase
- Account creation with Google/Apple sign-in
- Restaurant profile setup (name, locations, cuisine type)
- AI assistant introduction and discovery conversation

### Standardization Phase (5 Sections)
- **Clasificacion** — Restaurant type and operational profile
- **Configuracion** — Units, families, categories setup
- **Alineamiento** — Recipe upload and ingredient-to-inventory mapping
- **Estructura** — Inventory enrichment (units, conversion factors, families)
- **Normalizacion** — Automated validation and consistency checks

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

Zenet structures a restaurant through 5 progressive sections:

1. **Clasificacion** — Restaurant type, profile, and operational style
2. **Configuracion** — Measurement system (units, families, categories)
3. **Alineamiento** — Recipes mapped to inventory items
4. **Estructura** — Inventory enriched with metadata (units, factors, families)
5. **Normalizacion** — Validation and consistency checks

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

### Core Entities

- **restaurants** — Restaurant profile and metadata
- **locations** — Individual restaurant locations
- **recipes** — Standardized recipes
- **recipe_ingredients** — Ingredients in recipes
- **inventory_items** — Standardized inventory items
- **inventory_units** — Measurement units (kg, L, pza, box, etc.)
- **families** — Ingredient families (Lacteos, Carnes, etc.)
- **categories** — Item categories (Perecedero, No perecedero)
- **users** — User accounts and roles
- **user_restaurants** — User-restaurant relationships (multi-tenancy)

See `/docs/database/schema.md` for complete schema.

---

## Multi-Tenancy

Zenet supports multiple restaurants per account and multiple users per restaurant.

**Data Isolation:**
- PostgreSQL Row-Level Security (RLS) enforces restaurant-level isolation
- JWT includes `restaurant_id` for authorization
- All queries filtered by `user_restaurant_id`

**User Roles:**
- **Owner** — Full access (billing, team, all sections)
- **Manager** — Limited access (standardization, manual operativo)
- **Chef** — Standardization and manual operativo access
- **Admin** — Read-only access to data and exports

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

### v1.0 (Current)
- [x] Three-phase user experience
- [x] AI assistant integration
- [x] Five standardization sections
- [x] Manual Operativo dashboard
- [x] Multi-tenancy foundation
- [x] Basic authentication

### v1.1 (Next)
- [ ] File export (PDF, Excel)
- [ ] Team collaboration features
- [ ] Advanced KPI insights
- [ ] Batch operations

### v2.0 (Future)
- [ ] Forecasting module
- [ ] Supply chain optimization
- [ ] Advanced analytics
- [ ] POS integrations
- [ ] Mobile app

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
- **Production Strategy:** `/docs/production-strategy.md` — Technical architecture, stack decisions, deployment
- **Database Schema:** `/docs/database-schema.md` — Entity definitions, relationships, RLS policies
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
