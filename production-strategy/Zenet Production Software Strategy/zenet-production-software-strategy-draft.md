# Zenet Production Software Strategy

**Version:** Draft 1.0
**Status:** Pending Review

---

## Table of Contents

1. [Product Context](#1-product-context)
2. [System Architecture](#2-system-architecture)
3. [Frontend](#3-frontend)
4. [Backend](#4-backend)
5. [Database](#5-database)
6. [Multi-Tenancy](#6-multi-tenancy)
7. [AI and Prompt Engineering](#7-ai-and-prompt-engineering)
8. [Security](#8-security)
9. [Testing Strategy](#9-testing-strategy)
10. [CI/CD](#10-cicd)
11. [Deployment](#11-deployment)
12. [Monitoring and Observability](#12-monitoring-and-observability)
13. [Performance](#13-performance)
14. [UI/UX Strategy](#14-uiux-strategy)
15. [Accessibility](#15-accessibility)
16. [API Design and Versioning](#16-api-design-and-versioning)
17. [Error Handling](#17-error-handling)
18. [Documentation](#18-documentation)
19. [Version Tracking](#19-version-tracking)
20. [Sprint Planning and Development Process](#20-sprint-planning-and-development-process)

---

## 1. Product Context

### What Zenet Is

Zenet is a cognitive operational system for restaurants. It orders data, standardizes structures, normalizes information, builds an operational model, and creates a foundation for future automation. The system guides restaurant operators through a structured pipeline that transforms chaotic operational data into a coherent, standardized model.

### MVP Validation (Gradio)

A local, single-restaurant proof-of-concept was built to validate the core product idea:

- **6-section pipeline** guiding restaurant operators through operational standardization
- **AI agents** (Claude-powered) that propose inventory structures, recipes, and categories
- **Local SQLite database** storing session data
- **Gradio interface** for rapid development and iteration
- **No cloud infrastructure** (runs locally)
- **No authentication or payment** (session-based, free testing)

The MVP validated that: (a) the product concept solves real restaurant problems, (b) AI agents produce useful proposals, and (c) restaurant operators understand and value the guided workflow.

### Production Software

The production system is a cloud-based, multi-tenant SaaS platform that commercializes the validated MVP concept:

- **Web application** (Next.js) accessible globally via browser
- **Professional backend** (FastAPI) handling business logic and agent orchestration
- **PostgreSQL database** (Supabase) with row-level security for multi-tenancy
- **Real authentication** (Supabase Auth) with user accounts and team support
- **Monitoring and observability** (Sentry, Langfuse, UptimeRobot)
- **CI/CD pipeline** (GitHub Actions) for automated testing and deployment
- **Scalable infrastructure** (Vercel + Railway) capable of supporting growth
- **Payment integration** (Stripe) for SaaS billing

### Application Sections

The production software consists of the following sections:

**Core Pipeline (6 sections from MVP):**

| Section | Purpose |
|---------|---------|
| **Bienvenida** | Onboarding, restaurant profile creation, initial info capture |
| **Clasificacion** | Restaurant-type classification, suggested templates, operational diagnosis |
| **Configuracion** | Guided setup of recipe categories and inventory families |
| **Alineamiento** | Data ingestion (PDF, photo, text, Excel), normalization, unit conversion |
| **Estructura** | Structured representation of inventory with units, families, and categories |
| **Manual Operativo** | Operational manual visualization, data exploration, and Q&A |

**Additional Sections:**

| Section | Purpose |
|---------|---------|
| **Dashboard** | KPIs, operational metrics, inventory health, trends, and readiness indicators |
| **Settings** | Restaurant profile management, team members, subscription, and account settings |
| **Normalization** | *(Under evaluation)* Potential dedicated section for unit normalization and equivalence management |

### What Stays the Same from MVP

- Core product concept: AI agents proposing solutions, restaurant operator as user
- Core value proposition: Reduces operational chaos, improves inventory accuracy, enables data-driven decisions
- Tech foundation: Claude API for intelligence, Python backend, React-based frontend, relational database
- Pipeline sequence: Bienvenida through Manual Operativo

### What Changes from MVP

| Aspect | MVP | Production |
|--------|-----|------------|
| Architecture | Monolithic Gradio app | Decoupled: Frontend + Backend + Database |
| Database | Local SQLite | Multi-region PostgreSQL (Supabase) |
| Authentication | None (session-based) | Supabase Auth (JWT, teams) |
| Payments | None | Stripe integration |
| Data | Test data, ephemeral | Real restaurant data, backed up, recoverable |
| Migrations | Manual SQL | Alembic (automated) |
| Monitoring | None | Sentry, Langfuse, UptimeRobot |
| Scaling | Single instance | Auto-scaling infrastructure |
| Deployment | Local only | Vercel (frontend) + Railway (backend) |

---

## 2. System Architecture

### Architecture Diagram

```
                    Restaurant Operators
                           │
                    ┌──────┴──────┐
                    │   Browser   │
                    └──────┬──────┘
                           │ HTTPS
              ┌────────────┴────────────┐
              │                         │
     ┌────────┴────────┐      ┌────────┴────────┐
     │  Next.js (Vercel)│      │  FastAPI (Railway)│
     │  Frontend         │◄────►│  Backend          │
     │  - UI components  │ REST │  - Business logic │
     │  - State mgmt     │ API  │  - Agent orchestr.│
     │  - Auth (client)  │      │  - Auth (verify)  │
     └─────────────────-─┘      └────────┬─────────┘
                                         │
                              ┌──────────┴──────────┐
                              │                      │
                    ┌─────────┴────────┐   ┌────────┴────────┐
                    │ Supabase         │   │ Claude API       │
                    │ - PostgreSQL     │   │ - Agent LLM      │
                    │ - Auth           │   │ - Structured     │
                    │ - RLS            │   │   outputs        │
                    │ - Backups        │   └─────────────────-┘
                    └──────────────────┘
                              │
                    ┌─────────┴────────┐
                    │ Monitoring        │
                    │ - Sentry (errors) │
                    │ - Langfuse (AI)   │
                    │ - UptimeRobot     │
                    │ - PostHog (usage) │
                    └──────────────────-┘
```

### Tech Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Next.js 15+ (App Router), TypeScript | Web application |
| **UI Library** | shadcn/ui + Radix UI + Tailwind CSS | Component system |
| **Backend** | FastAPI (Python 3.13) | REST API, business logic |
| **Database** | Supabase (PostgreSQL) | Data persistence |
| **Authentication** | Supabase Auth (JWT) | User management |
| **AI/LLM** | Anthropic Claude API | Agent intelligence |
| **Payments** | Stripe | Subscription billing |
| **Frontend Hosting** | Vercel | CDN, global deployment |
| **Backend Hosting** | Railway | Container hosting |
| **CI/CD** | GitHub Actions | Automated pipelines |
| **Error Tracking** | Sentry | Runtime error monitoring |
| **AI Monitoring** | Langfuse | LLM cost and trace tracking |
| **Uptime** | UptimeRobot | Endpoint health checks |
| **Analytics** | PostHog | User behavior tracking |

---

## 3. Frontend

### Tech Stack

```json
{
  "framework": "Next.js 15+ (App Router)",
  "language": "TypeScript",
  "ui_library": "shadcn/ui + Radix UI",
  "styling": "Tailwind CSS",
  "state_management": "Zustand",
  "data_fetching": "TanStack Query (React Query)",
  "forms": "react-hook-form + zod",
  "http_client": "axios",
  "auth": "Supabase Auth (JWT)",
  "icons": "lucide-react",
  "animations": "Framer Motion",
  "component_docs": "Storybook",
  "testing": "vitest + @testing-library/react",
  "deployment": "Vercel"
}
```

### Project Structure

```
frontend/
├── app/                               # Next.js App Router
│   ├── layout.tsx                     # Root layout (nav, auth check)
│   ├── page.tsx                       # Landing page (pre-login)
│   ├── (auth)/                        # Auth group
│   │   ├── login/page.tsx
│   │   ├── signup/page.tsx
│   │   └── forgot-password/page.tsx
│   └── (dashboard)/                   # Protected routes (require login)
│       ├── layout.tsx                 # Dashboard layout (sidebar, nav)
│       ├── page.tsx                   # Dashboard home
│       ├── bienvenida/page.tsx
│       ├── clasificacion/page.tsx
│       ├── configuracion/page.tsx
│       ├── alineamiento/page.tsx
│       ├── estructura/page.tsx
│       ├── manual-operativo/page.tsx
│       ├── settings/page.tsx
│       ├── data/page.tsx
│       └── support/page.tsx
│
├── components/
│   ├── ui/                            # shadcn/ui components
│   ├── sections/                      # Section-specific components
│   │   ├── bienvenida/
│   │   ├── clasificacion/
│   │   ├── alineamiento/
│   │   └── estructura/
│   ├── shared/                        # Reusable components
│   │   ├── navbar.tsx
│   │   ├── sidebar.tsx
│   │   ├── progress-stepper.tsx
│   │   ├── agent-chat.tsx
│   │   ├── table-editor.tsx
│   │   ├── file-upload.tsx
│   │   └── error-boundary.tsx
│   └── providers.tsx                  # Root providers (Auth, Query, Theme)
│
├── lib/
│   ├── api.ts                         # API client (axios + interceptors)
│   ├── auth.ts                        # Supabase Auth helpers
│   ├── supabase.ts                    # Supabase client setup
│   ├── hooks/                         # Custom React hooks
│   ├── types/                         # TypeScript type definitions
│   └── utils.ts                       # Utility functions
│
├── styles/
│   ├── globals.css                    # Tailwind + global styles
│   └── tokens.ts                      # Design tokens
│
├── middleware.ts                      # Auth middleware (route protection)
└── .env.local                         # Environment variables
```

### Key Patterns

- **Protected routes:** Middleware checks JWT on every request to `/dashboard/*`
- **API client:** Axios with interceptors for auto-attaching auth tokens and handling 401 redirects
- **State management:** Zustand for auth/global state; TanStack Query for server state (caching, refetching)
- **Forms:** react-hook-form with Zod schemas for type-safe validation
- **Error boundaries:** Catch and display user-friendly error messages
- **Code splitting:** Dynamic imports for section components (lazy loading)
- **Responsive design:** Mobile-first with Tailwind breakpoints

### Environment Variables

```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=https://api.zenetapp.com
```

---

## 4. Backend

### Tech Stack

| Need | Tool | Rationale |
|------|------|-----------|
| Framework | FastAPI | Fast, async, auto-generated OpenAPI docs |
| Auth | Supabase Auth | Integrated with database, JWT |
| Validation | Pydantic | Type-safe request/response models |
| Migrations | Alembic | Schema versioning for PostgreSQL |
| Testing | pytest + pytest-asyncio | Industry standard |
| Environment | python-dotenv | Manage secrets |
| Payment | stripe-python | Stripe integration |
| Logging | Python logging + Sentry | Error tracking |
| CORS | fastapi-cors | Allow frontend requests |
| Rate limiting | slowapi | Prevent API abuse |

### Project Structure

```
backend/
├── app.py                             # FastAPI entry point
├── config.py                          # Settings (DB, API keys, env)
├── requirements.txt                   # Dependencies
├── .env                               # Secrets (never committed)
│
├── api/
│   ├── routes/
│   │   ├── auth.py                    # Authentication endpoints
│   │   ├── restaurants.py             # Restaurant CRUD
│   │   ├── inventory.py               # Inventory endpoints
│   │   ├── recipes.py                 # Recipe endpoints
│   │   ├── agents.py                  # Agent execution
│   │   └── billing.py                 # Stripe integration
│   ├── middleware/
│   │   ├── auth.py                    # JWT verification
│   │   └── tenant.py                  # Multi-tenancy isolation
│   └── dependencies.py               # Shared dependencies (DB, auth)
│
├── models/                            # Pydantic models
│   ├── user.py
│   ├── restaurant.py
│   ├── inventory.py
│   └── billing.py
│
├── services/                          # Business logic
│   ├── auth_service.py
│   ├── restaurant_service.py
│   ├── agent_service.py
│   └── billing_service.py
│
├── db/
│   ├── connection.py                  # Supabase connection
│   ├── migrations/                    # Alembic migrations
│   └── models.py                      # SQLAlchemy ORM models (if needed)
│
└── tests/
    ├── test_auth.py
    ├── test_restaurants.py
    └── test_agents.py
```

### Key Patterns

- **Route versioning:** All endpoints prefixed with `/api/v1/`
- **Dependency injection:** `Depends(get_current_user)` for auth on all protected routes
- **Pydantic validation:** All request/response bodies validated with Pydantic models
- **Service layer:** Routes call services; services contain business logic; services call database
- **Health endpoints:** `/health` and `/health/db` for monitoring
- **Rate limiting:** Agent endpoints limited (e.g., 10 requests/minute per user)
- **CORS:** Configured to allow only `zenetapp.com` origin

### Database Client Strategy

The backend interacts with Supabase PostgreSQL via the **Supabase Python client** for initial development. If query complexity grows, migration to **SQLAlchemy ORM** with **Alembic** for schema migrations is planned.

---

## 5. Database

### Database Provider

**Supabase** (managed PostgreSQL) provides:

- Managed PostgreSQL instance with automated backups
- Built-in authentication (Supabase Auth)
- Row-Level Security (RLS) for multi-tenancy
- Connection pooling (automatic)
- Dashboard for query monitoring and management
- Point-in-time recovery

### Schema Design Principles

- Every tenant-scoped table includes a `restaurant_id` foreign key
- Reference tables (units, categories, restaurant types) are shared across tenants
- All tables include `created_at` and `updated_at` timestamps
- Foreign keys enforce referential integrity
- Indexes are created on all frequently filtered columns

### Core Tables

**Tenant-scoped tables** (filtered by `restaurant_id` via RLS):

- `restaurant` — Restaurant profile (tenant root)
- `inventory_item` — Inventory items with stock/purchase units
- `recipe` — Recipes
- `ingredient` — Recipe ingredients linked to inventory items
- `family_inventory` — Inventory families per restaurant
- `category_recipe` — Recipe categories per restaurant
- `classification` — Restaurant classification data
- `audit_log` — Change tracking per restaurant

**Shared reference tables** (global, read-only for tenants):

- `inventory_unit` — Standard and custom measurement units
- `inventory_category` — Perecedero / No perecedero
- `restaurant_type` — Restaurant type definitions
- `recipe_unit` — Recipe measurement units

### Indexing Strategy

Indexes are created on:

- All `restaurant_id` columns (primary tenant filter)
- All foreign key columns
- Frequently filtered columns (`category_id`, `family_id`)
- Text search columns (`name` with GIN index for full-text search, if needed)

Composite indexes for common query patterns:

```sql
CREATE INDEX idx_inventory_item_restaurant_category
  ON inventory_item(restaurant_id, category_id);
```

### Query Optimization

- Avoid N+1 queries: Use Supabase's `select("*, related_table(*)")` for joins
- Fetch only needed columns: Use `select("id, name, category_id")` instead of `select("*")`
- Connection pooling: Handled automatically by Supabase

### Backups

- **Daily automated backups** retained for 7 days
- **Weekly backups** retained for 4 weeks
- **Point-in-time recovery** available on Pro plan
- **Manual backups** via `pg_dump` for additional safety

### Schema Evolution

Schema changes are managed through migration files (SQL or Alembic):

- **Safe migrations:** Adding nullable columns, creating indexes, adding tables
- **Risky migrations:** Renaming columns, dropping columns (require careful coordination with code deployment)
- All migrations are tested on staging before production
- Rollback procedures are documented for each migration

---

## 6. Multi-Tenancy

### Approach: Row-Level Security (RLS)

All tenant data is stored in a single PostgreSQL database. Data isolation is enforced at the database level using PostgreSQL's Row-Level Security (RLS), which automatically filters rows based on the authenticated user.

### How It Works

1. Restaurant manager authenticates via Supabase Auth
2. User ID (`auth.uid()`) is linked to `restaurant_id`
3. RLS policies filter all queries to return only the authenticated restaurant's data
4. Even if application code omits a `WHERE` clause, PostgreSQL enforces isolation

```sql
ALTER TABLE inventory_item ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own inventory"
  ON inventory_item FOR SELECT
  USING (restaurant_id = auth.uid());

CREATE POLICY "Users create own inventory items"
  ON inventory_item FOR INSERT
  WITH CHECK (restaurant_id = auth.uid());

CREATE POLICY "Users update own inventory items"
  ON inventory_item FOR UPDATE
  USING (restaurant_id = auth.uid());
```

### Team Access (Multi-User Per Restaurant)

A `user_restaurant` mapping table supports multiple users per restaurant:

```sql
CREATE TABLE user_restaurant (
  user_id UUID REFERENCES auth.users(id),
  restaurant_id UUID REFERENCES restaurant(id),
  role TEXT CHECK (role IN ('owner', 'manager', 'chef')),
  UNIQUE(user_id, restaurant_id)
);
```

RLS policies check this mapping:

```sql
CREATE POLICY "Team members see own restaurant inventory"
  ON inventory_item FOR SELECT
  USING (
    restaurant_id IN (
      SELECT restaurant_id FROM user_restaurant WHERE user_id = auth.uid()
    )
  );
```

### Security Guarantees

- RLS is enforced at the database level — application code cannot bypass it
- Even developer mistakes (forgetting to filter by `restaurant_id`) cannot expose other tenants' data
- Backend always extracts `user.id` from JWT token, never from request parameters

### Scaling

RLS scales well to thousands of tenants on a single database. If scaling beyond that becomes necessary, migration to schema-per-tenant or database sharding can be evaluated.

---

## 7. AI and Prompt Engineering

### Agent Architecture

The production system retains the MVP's agent framework:

- **BaseAgent** abstract class with `run()`, `validate()`, tool calling, memory, and retry logic
- **create_agent()** factory for instantiation
- **ConversationMemory** for per-session chat history
- **ClaudeProvider** for LLM interaction via the Anthropic SDK

Each pipeline section has a dedicated agent:

| Agent | Section | Primary Function |
|-------|---------|------------------|
| WelcomeAgent | Bienvenida | Onboarding, restaurant info capture |
| ClassificationAgent | Clasificacion | Restaurant type classification |
| ConfigurationAgent | Configuracion | Category and family setup |
| ConsistencyCheckAgent | Configuracion | Validate configuration coherence |
| AlignmentAgent | Alineamiento | Data ingestion, normalization |
| StructuringAgent | Estructura | Inventory structuring with units/families |
| ManualOperativoAgent | Manual Operativo | Data visualization, Q&A |

### Tools and Technologies

| Need | Tool | Purpose |
|------|------|---------|
| Prompt versioning | Langfuse + Git | Version control and experimentation |
| Agent orchestration | Custom framework (BaseAgent) | Multi-step agent workflows |
| Prompt testing | promptfoo | A/B test different prompts |
| Cost tracking | Langfuse | Monitor tokens and Claude API costs |
| Observability | Langfuse traces | Debug agent behavior |
| LLM calls | Anthropic SDK (`anthropic`) | Direct Claude API interaction |

### Prompt Management

- Prompts are versioned in Git (one file per agent, per version)
- Langfuse traces track which prompt version produced each output
- promptfoo enables systematic comparison of prompt variants
- Default model: Claude Sonnet 4.6 (`claude-sonnet-4-6`) for production agents

### Production Considerations

- **Retry logic:** Agents retry on transient API errors (rate limits, timeouts)
- **Structured outputs:** All agents return structured data (JSON), not free-form text
- **Cost monitoring:** Langfuse tracks input/output tokens per restaurant per agent per month
- **Fallback:** If Claude API is unavailable, agents return a user-friendly error message
- **No LangChain/LangGraph dependency:** Custom framework is simpler and sufficient for current agent patterns. LangGraph is considered only if complex multi-agent orchestration becomes necessary.

---

## 8. Security

### Authentication

- **Supabase Auth** handles user registration, login, password reset, and JWT token management
- **JWT tokens** are validated on every backend request via FastAPI middleware
- Backend extracts `user.id` from the token — never from request parameters

### Authorization

- **Row-Level Security (RLS)** enforces data isolation at the database level (see Multi-Tenancy section)
- **Role-based access:** Owner, Manager, Chef roles defined in `user_restaurant` table
- Endpoint-level checks enforce role requirements where needed

### Input Validation

- **Pydantic models** validate all incoming request bodies with type checking, length limits, and regex patterns
- Example: `user_message` capped at 5000 characters; `category` validated against allowed values

### Rate Limiting

- Agent endpoints limited to prevent abuse (e.g., 10 requests/minute per user)
- Implemented via `slowapi` middleware

### CORS

- Configured to allow requests only from `zenetapp.com` (production frontend origin)
- Methods restricted to `GET`, `POST`, `PUT`, `DELETE`
- Credentials allowed for cookie-based auth

### Secrets Management

- All API keys stored as environment variables (never hardcoded)
- `.env` files excluded from version control via `.gitignore`
- Production secrets stored in Railway and Vercel dashboard (encrypted)
- GitHub Secrets used for CI/CD pipeline

### Transport Security

- HTTPS enforced on all connections (auto-provisioned by Vercel, Railway, and Supabase)
- No HTTP endpoints exposed

### Dependency Scanning

- **GitHub Dependabot** automatically creates PRs for vulnerable dependencies
- **pip audit** and **npm audit** run in CI/CD pipeline
- **TruffleHog** scans for accidentally committed secrets

### Security Checklist (Pre-Launch)

- [ ] Supabase RLS enabled on all tables
- [ ] JWT token validation on all endpoints
- [ ] Input validation (Pydantic models) on all endpoints
- [ ] Environment variables for all secrets
- [ ] Rate limiting on agent endpoints
- [ ] CORS configured (allow only `zenetapp.com`)
- [ ] `.env` in `.gitignore`
- [ ] Privacy policy and Terms of Service published
- [ ] HTTPS verified on all endpoints
- [ ] SQL injection prevention (parameterized queries)
- [ ] No hardcoded API keys in codebase

---

## 9. Testing Strategy

### Testing Layers

| Layer | Tool | Purpose |
|-------|------|---------|
| **Unit Tests** | `pytest` (backend) + `vitest` (frontend) | Test individual functions, business logic |
| **Integration Tests** | `pytest` + FastAPI `TestClient` | Test API endpoints with real/mock database |
| **E2E Tests** | Playwright | Test full workflows through browser |
| **API Contract Tests** | `pytest` + response assertions | Ensure API responses match schema |

### Coverage Targets

- **Unit tests:** 80%+ code coverage
- **Integration tests:** All API endpoints covered with happy path + error cases
- **E2E tests:** Critical user flows only (sign up, complete one section, save data)

### E2E Focus Areas

- Happy path: User completes one full section end-to-end
- Edge cases: Empty inputs, network errors, session expiration
- Skip: Minor UI interactions, trivial branches

### Testing Tools

- **Backend:** `pytest`, `pytest-asyncio`, `httpx` (async test client)
- **Frontend:** `vitest`, `@testing-library/react`, `jest-axe` (accessibility)
- **E2E:** Playwright (parallel execution, multi-browser support)
- **Coverage:** `coverage.py` (backend), `vitest` built-in (frontend)

### Why Playwright over Cypress

- Parallel test execution (faster CI/CD)
- Multi-browser support (Chrome, Firefox, Safari)
- More stable in headless CI/CD environments
- Python support (aligns with backend language)

---

## 10. CI/CD

### Pipeline Overview

```
Developer pushes to GitHub
        ↓
GitHub Actions triggered
        ↓
    ┌───┴──────────┬──────────┐
    ↓              ↓          ↓
  Lint          Tests      Security
    ↓              ↓          ↓
    └───┬──────────┴──────────┘
        ↓
   All passed?
        ↓
   Build artifacts
        ↓
   Deploy to production
        ↓
   Health checks
        ↓
   Monitor
```

### Workflows

**Backend CI (`backend-test.yml`):**
- Trigger: Push to `main` or PR
- Steps: Lint (ruff + mypy) → Unit tests (pytest) → Coverage check (80%+)

**Frontend CI (`frontend-test.yml`):**
- Trigger: Push to `main` or PR
- Steps: Lint (ESLint) → Type check (TypeScript) → Unit tests (vitest) → Build → E2E tests (Playwright)

**Security Scan (`security.yml`):**
- Trigger: Push to `main`, weekly schedule
- Steps: Secret scanning (TruffleHog) → Python vulnerability check (safety) → Node vulnerability check (npm audit)

**Backend Deploy (`backend-deploy.yml`):**
- Trigger: Push to `main` (backend paths)
- Steps: Deploy to Railway → Health check → Slack notification

**Frontend Deploy (`frontend-deploy.yml`):**
- Trigger: Push to `main` (frontend paths)
- Steps: Build Next.js → Deploy to Vercel → Slack notification

### Branch Protection

- `main` branch requires PR reviews before merging
- All status checks (lint, tests, security) must pass
- Direct pushes to `main` are blocked

### CI/CD Checklist

- [ ] GitHub repository configured with branch protection
- [ ] GitHub Secrets added (API keys, deploy tokens)
- [ ] Backend lint + test workflow running
- [ ] Frontend lint + test workflow running
- [ ] Security scanning workflow running
- [ ] Auto-deploy on `main` push (Railway + Vercel)
- [ ] Health checks after each deployment
- [ ] Slack notifications on deploy success/failure
- [ ] Rollback procedure documented and tested

---

## 11. Deployment

### Infrastructure

| Component | Platform | Region |
|-----------|----------|--------|
| Frontend | Vercel | Global CDN |
| Backend | Railway | us-east-1 |
| Database | Supabase | us-east-1 |
| Domain | zenetapp.com | — |

### Deployment Environments

| Environment | Purpose | URL |
|-------------|---------|-----|
| Local | Development | localhost:3000 / localhost:8000 |
| Staging | Pre-production testing | staging.zenetapp.com |
| Production | Live for users | zenetapp.com / api.zenetapp.com |

### Deployment Process

1. Developer creates feature branch and opens PR
2. GitHub Actions runs lint, tests, and security scans
3. PR reviewed and merged to `main`
4. Auto-deploy triggers:
   - Backend: Docker image built and deployed to Railway
   - Frontend: Next.js built and deployed to Vercel
5. Health checks verify deployment success
6. Team notified via Slack

### Rollback

- **Backend:** `railway rollback` reverts to previous deployment
- **Frontend:** Vercel dashboard allows one-click rollback to any previous deployment
- **Database:** Supabase point-in-time recovery for data issues

### Domain and SSL

- Domain: `zenetapp.com` (frontend) and `api.zenetapp.com` (backend)
- SSL/TLS certificates auto-provisioned and renewed by Vercel and Railway
- No manual certificate management required

### Backend Dockerfile

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --no-dev
COPY backend/ ./backend/
COPY core/ ./core/
CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Scaling Strategy

| Stage | Infrastructure | Capacity |
|-------|---------------|----------|
| Launch | Railway 1 instance + Vercel free + Supabase Pro | < 100 restaurants |
| Growth | Railway 2GB instance + Vercel Pro + Supabase Dedicated | 100-1000 restaurants |
| Scale | Multi-region Railway + Supabase Enterprise | 1000+ restaurants |

---

## 12. Monitoring and Observability

### Monitoring Stack

| Tool | Purpose | Priority |
|------|---------|----------|
| **Sentry** | Error tracking (backend + frontend) | Critical |
| **Langfuse** | AI/LLM cost tracking, agent traces | Critical |
| **UptimeRobot** | Endpoint health monitoring | Important |
| **PostHog** | User analytics, feature usage | Important |

### Sentry (Error Tracking)

- Auto-captures all unhandled exceptions in FastAPI via middleware
- Frontend errors captured via `@sentry/nextjs` SDK
- Alerts configured for error rate spikes
- Source maps uploaded for readable stack traces

### Langfuse (AI Monitoring)

- Traces every agent run: input, output, tokens used, latency
- Tracks cost per restaurant, per agent, per month
- Enables prompt version comparison
- Dashboard for monitoring Claude API spend

### UptimeRobot (Health Monitoring)

- Pings `/health` endpoint every 5 minutes
- Alerts via email/Slack if endpoint is down
- Tracks uptime percentage (target: 99%+)

### PostHog (User Analytics)

- Tracks which sections users complete
- Measures time-to-completion per section
- Identifies drop-off points in the pipeline
- Feature flag support for gradual rollouts

### Health Check Endpoints

```
GET /health          → {"status": "ok", "version": "1.0.0"}
GET /health/db       → {"status": "ok", "database": "connected"}
```

---

## 13. Performance

### Targets

| Metric | Target |
|--------|--------|
| API response time (p95) | < 500ms |
| Agent response time (p95) | < 2 seconds |
| Frontend page load | < 3 seconds |
| Database query time | < 100ms |
| Lighthouse score | 90+ |

### Backend Optimization

- **Connection pooling:** Supabase handles automatically
- **Caching:** Cache restaurant context data for repeated agent calls
- **Async handlers:** Use `asyncio.to_thread()` for blocking agent operations
- **Profiling:** `py-spy` for identifying slow functions during development

### Database Optimization

- **Indexes** on all frequently filtered columns (see Database section)
- **Avoid N+1 queries:** Use join syntax in Supabase client
- **Select only needed columns:** Reduce data transfer
- **Monitor slow queries:** Supabase dashboard + `pg_stat_statements`

### Frontend Optimization

- **Code splitting:** Dynamic imports for section components
- **Image optimization:** `next/image` with automatic resizing
- **Font optimization:** `next/font` for zero-FOUT loading
- **Caching:** TanStack Query handles client-side data caching with stale-while-revalidate
- **Core Web Vitals:** Monitor via Vercel Analytics

### Load Testing

- **Tool:** k6 for API load testing
- **Scenarios:** Simulate 10-50 concurrent users running agents
- **Thresholds:** p95 response time < 2s, error rate < 1%
- Load testing runs before major releases

---

## 14. UI/UX Strategy

### Design System

| Layer | Tool | Purpose |
|-------|------|---------|
| Component Library | shadcn/ui (Radix UI) | Pre-built, accessible components |
| Styling | Tailwind CSS | Utility-first CSS |
| Icons | lucide-react | Consistent icon set |
| Forms | react-hook-form + zod | Type-safe form handling |
| Animations | Framer Motion | Smooth transitions |
| Design Tokens | Figma + CSS variables | Color, spacing, typography system |
| Component Docs | Storybook | Visual component documentation |
| Design Tool | Figma | Design specs and handoff |

### Design Workflow

1. Design in Figma (define tokens, create specs)
2. Export tokens to Tailwind/CSS variables
3. Implement with shadcn/ui components
4. Document in Storybook
5. Test for accessibility
6. Deploy to Vercel

### Component Architecture

- **`ui/`** — shadcn/ui imported components (button, input, card, dialog, table)
- **`sections/`** — Section-specific components (bienvenida/restaurant-form.tsx)
- **`shared/`** — Reusable patterns (navbar, sidebar, progress-stepper, agent-chat)

### Responsive Design

- Mobile-first approach using Tailwind breakpoints
- Two-column layout (chat + table) collapses to single column on mobile
- Navigation sidebar collapses to hamburger menu on mobile

### User Experience Patterns

- **Progress stepper:** Shows completed, active, and pending sections
- **Agent chat panel:** Reusable chat component across all agent sections
- **Editable table:** Proposal review table with inline editing
- **File upload:** Drag-and-drop with support for PDF, Excel, and images
- **Loading states:** Skeleton components while data loads
- **Error states:** User-friendly error messages with retry options

---

## 15. Accessibility

### Standard

Target: **WCAG 2.1 Level AA** compliance.

### Core Principles (POUR)

- **Perceivable:** High contrast (4.5:1 minimum), alt text on images, no color-only indicators
- **Operable:** Full keyboard navigation, visible focus indicators, no keyboard traps
- **Understandable:** Clear labels, descriptive error messages, consistent navigation
- **Robust:** Semantic HTML, proper ARIA attributes, works with screen readers

### Implementation

- shadcn/ui components include accessibility features by default (ARIA, keyboard nav, focus management)
- All form inputs have associated `<label>` elements
- Error messages use `role="alert"` for screen reader announcement
- Skip links provided for main content navigation
- Focus indicators visible on all interactive elements
- `aria-live` regions for dynamic content updates (agent responses)

### Testing

- **Automated:** `axe-core` tests in CI/CD pipeline
- **Manual:** Keyboard navigation testing, screen reader testing (VoiceOver/NVDA)
- **Lighthouse:** Accessibility score target: 90+
- **Browser extensions:** axe DevTools, WAVE for development-time checks

### Accessibility Checklist

- [ ] Semantic HTML used throughout (`<button>`, `<nav>`, `<main>`, `<form>`)
- [ ] Proper heading hierarchy (H1 → H2 → H3, no skipping)
- [ ] All form inputs have labels
- [ ] Color contrast ≥ 4.5:1 for text
- [ ] All interactive elements keyboard accessible
- [ ] Focus indicators visible
- [ ] Images have descriptive alt text
- [ ] Error messages clear and announced to screen readers
- [ ] Skip links present
- [ ] axe-core tests passing in CI/CD

---

## 16. API Design and Versioning

### Versioning Strategy

All API endpoints are prefixed with `/api/v1/`. This allows future breaking changes to be introduced as `/api/v2/` without disrupting existing clients.

### Endpoint Structure

```
POST   /api/v1/auth/signup              # User registration
POST   /api/v1/auth/login               # User login
POST   /api/v1/auth/logout              # User logout
POST   /api/v1/auth/forgot-password     # Password reset

GET    /api/v1/restaurants/me            # Get current restaurant
POST   /api/v1/restaurants               # Create restaurant
PUT    /api/v1/restaurants/me            # Update restaurant

GET    /api/v1/inventory-items           # List inventory items
POST   /api/v1/inventory-items           # Create inventory items
PUT    /api/v1/inventory-items/:id       # Update inventory item
DELETE /api/v1/inventory-items/:id       # Delete inventory item

GET    /api/v1/recipes                   # List recipes
POST   /api/v1/recipes                   # Create recipe
PUT    /api/v1/recipes/:id               # Update recipe
DELETE /api/v1/recipes/:id               # Delete recipe

POST   /api/v1/agents/welcome            # Run welcome agent
POST   /api/v1/agents/classification     # Run classification agent
POST   /api/v1/agents/configuration      # Run configuration agent
POST   /api/v1/agents/alignment          # Run alignment agent
POST   /api/v1/agents/structuring        # Run structuring agent
POST   /api/v1/agents/manual-operativo   # Run manual operativo agent

GET    /api/v1/dashboard/kpis            # Get readiness KPIs
GET    /api/v1/dashboard/metrics         # Get operational metrics

GET    /health                           # Health check
GET    /health/db                        # Database health check
```

### Versioning Lifecycle

- Launch with `/api/v1/` exclusively
- When breaking changes are needed, create `/api/v2/` endpoints
- Both versions run simultaneously during migration period
- Deprecated versions are announced and given a sunset date
- Deprecated endpoints return `410 Gone` after sunset

### Documentation

- FastAPI auto-generates OpenAPI (Swagger) documentation at `/docs`
- ReDoc alternative available at `/redoc`
- API spec exportable as JSON for external tooling

---

## 17. Error Handling

### Backend Error Strategy

- **Pydantic validation errors:** Return `422 Unprocessable Entity` with field-level details
- **Authentication errors:** Return `401 Unauthorized` with generic message (no information leakage)
- **Authorization errors:** Return `403 Forbidden`
- **Not found:** Return `404 Not Found`
- **Rate limiting:** Return `429 Too Many Requests`
- **Internal errors:** Return `500 Internal Server Error` with generic message; detailed error logged to Sentry
- **Agent errors:** Caught and returned as user-friendly messages; no raw exception traces exposed

### Frontend Error Strategy

- **Error boundaries:** Catch rendering errors and display fallback UI
- **API errors:** Intercepted by axios; 401 redirects to login, others show toast notification
- **Network errors:** "Connection lost" message with retry button
- **Form errors:** Inline validation messages below each field
- **Agent errors:** "Hubo un problema al conectar con el asistente. Intenta de nuevo." with retry option

### Principles

- Never expose stack traces, database errors, or internal details to users
- Log full error context to Sentry for debugging
- Provide actionable error messages ("Intenta de nuevo" rather than "Error 500")
- Graceful degradation: If a non-critical service fails, the rest of the app continues working

---

## 18. Documentation

### Documentation Types

| Audience | Type | Tool/Location |
|----------|------|---------------|
| Backend developers | Architecture, API docs | GitHub `docs/` + Swagger |
| Frontend developers | Component library | Storybook |
| DevOps | Deployment runbooks | GitHub `docs/DEPLOYMENT.md` |
| Support team | Troubleshooting guides | Internal wiki (Notion) |
| Restaurant operators | User guides, FAQ | Knowledge base (Zendesk or similar) |

### Repository Documentation

```
docs/
├── README.md                          # Start here
├── GETTING_STARTED.md                 # Developer setup
├── ARCHITECTURE.md                    # System design
├── API.md                             # API endpoints (supplements Swagger)
├── DATABASE.md                        # Schema docs
├── DEPLOYMENT.md                      # Deployment procedures
├── MONITORING.md                      # Observability setup
├── TROUBLESHOOTING.md                 # Common issues
├── RUNBOOK.md                         # Operations procedures
└── CONTRIBUTING.md                    # How to contribute
```

### API Documentation

- Auto-generated via FastAPI at `/docs` (Swagger UI) and `/redoc` (ReDoc)
- All endpoints include summary, description, request/response examples, and error codes
- OpenAPI spec exportable for external tools

### User Documentation

- In-app help tooltips on key features
- Knowledge base with guides per section
- FAQ covering common questions
- Support email for direct assistance

---

## 19. Version Tracking

### Semantic Versioning

Format: `MAJOR.MINOR.PATCH`

```
0.1.0
│ │ └─ Patch (bug fixes, hotfixes)
│ └─── Minor (new features, backwards compatible)
└───── Major (breaking changes, incompatible updates)
```

### Version Tracking Mechanism

- **Source of truth:** `pyproject.toml` for backend, `package.json` for frontend
- **Git tags:** Every release is tagged (e.g., `v1.0.0`)
- **CHANGELOG.md:** Documents what changed in each version
- **`__version__`:** Exposed in backend code for runtime access

### Versioning Rules

| Event | Action |
|-------|--------|
| Bug fix | Bump patch (e.g., `1.0.0 → 1.0.1`) |
| New section or feature | Bump minor (e.g., `1.0.0 → 1.1.0`) |
| Breaking API change | Bump major (e.g., `1.x.x → 2.0.0`) |
| After bumping | Update CHANGELOG.md + create git tag |

---

## 20. Sprint Planning and Development Process

### Process Flow

```
1. Production PRD (1 document, high-level strategy)
        ↓
2. Sprint Plans (one per section + 1 polish sprint)
        ↓
3. TaskMaster Sprint Task (parent task)
        ↓
4. Sub-tasks for each story (5-8 per sprint)
        ↓
5. Sprint execution
   ├── Work through stories sequentially
   ├── Daily standup + status updates
   ├── Deploy to staging
   ├── Deploy to production
   ├── Demo + retrospective
   └── Sprint analysis
        ↓
6. Next sprint
```

### Sprint Structure

Each sprint delivers one complete pipeline section with:

- **Backend (2-3 days):** API endpoints, database queries, RLS policies, unit tests
- **Frontend (2-3 days):** Pages, forms, components, component tests
- **Integration (1 day):** E2E tests, API + frontend working together, staging deployment
- **Testing + QA (1 day):** Manual smoke test, performance check, accessibility audit
- **Deployment (1 day):** Production deployment, monitoring verification, documentation

### Sprint Cadence

- **Sprint duration:** 3 weeks
- **Delivery model:** Rolling releases (one section per sprint)
- **Review:** Demo to stakeholders at sprint end
- **Retrospective:** What went well, what to improve

### Polish Sprint

After all pipeline sections are shipped, a dedicated polish sprint addresses:

- Performance optimization (meeting target metrics)
- Bug fixes accumulated during feature sprints
- Accessibility audit and remediation
- Technical debt cleanup
- Documentation completion
- Monitoring fine-tuning

### Definition of Done (Per Sprint)

- [ ] All stories completed and code merged to `main`
- [ ] Unit tests passing with 80%+ coverage
- [ ] E2E tests passing for critical flows
- [ ] Code reviewed (at least 1 approval)
- [ ] Deployed to staging and verified
- [ ] Deployed to production
- [ ] Health checks passing
- [ ] Monitoring alerts configured
- [ ] Documentation updated
- [ ] No critical bugs in backlog

---

## Appendix A: Environment Variables

### Backend (Railway)

```
ANTHROPIC_API_KEY=sk-...
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
DATABASE_URL=postgresql://...
ENVIRONMENT=production
LOG_LEVEL=info
SENTRY_DSN=https://...
LANGFUSE_API_KEY=pk-...
STRIPE_SECRET_KEY=sk_live_...
```

### Frontend (Vercel)

```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=https://api.zenetapp.com
NEXT_PUBLIC_SENTRY_DSN=https://...
NEXT_PUBLIC_POSTHOG_KEY=phc_...
```

### GitHub Secrets (CI/CD)

```
RAILWAY_TOKEN
VERCEL_TOKEN
SUPABASE_SERVICE_KEY
ANTHROPIC_API_KEY
SENTRY_DSN
```

---

## Appendix B: Cost Estimates

| Service | Estimated Cost | Usage |
|---------|---------------|-------|
| Railway (backend) | $5-50/mo | FastAPI server |
| Vercel (frontend) | $0-20/mo | Next.js hosting |
| Supabase (database) | $25-250/mo | PostgreSQL + Auth |
| Anthropic (Claude API) | $50-200/mo | Agent LLM calls |
| Sentry | $0 (free tier) | Error tracking |
| Langfuse | $0 (free tier) | AI monitoring |
| UptimeRobot | $0 (free tier) | Health checks |
| PostHog | $0 (free tier) | Analytics |
| Domain (zenetapp.com) | $10-15/yr | Domain registration |
| **Total (MVP stage)** | **~$100-500/mo** | |

---

## Appendix C: Success Metrics

| Metric | Target |
|--------|--------|
| Uptime | 99%+ |
| API response time (p95) | < 500ms |
| Agent response time (p95) | < 2 seconds |
| Frontend Lighthouse score | 90+ |
| WCAG 2.1 AA compliance | Yes |
| Test coverage (backend) | 80%+ |
| Zero critical security vulnerabilities | Yes |
| Monthly churn | < 10% |
