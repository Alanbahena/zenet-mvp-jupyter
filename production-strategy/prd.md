<context>
# Overview

Zenet is a cognitive operating system for restaurant back-of-house operations. It is a multi-tenant SaaS platform that guides restaurant operators through standardizing their recipes, inventory, and processes — then generates a living operational manual (Manual Operativo) with KPIs and AI insights.

The production software rebuilds the validated Gradio MVP as a full-stack web application. The MVP proved that the AI-guided, section-by-section pipeline works: operators don't need to understand data modeling — the AI structures their messy real-world knowledge into clean operational data.

## What Zenet Is
1. **Centralizes** dispersed operations
2. **Standardizes** processes into clear, replicable workflows
3. **Automates** repetitive tasks with intelligent flows
4. **Interprets** operational data (doesn't just store it)
5. **Accompanies** day-to-day operations with virtual assistance

## What Zenet Is NOT
- Not a POS (point of sale)
- Not an isolated inventory app
- Not a complex enterprise ERP
- Not software you "install and figure out"

## Target Segment
- Independent restaurants with 1–5 locations
- In growth/expansion phase
- Casual dining (primary), Gourmet/Fine Dining (secondary)
- Geography: Tijuana (initial) → Baja California → Northwest Mexico → LATAM

## User Personas
1. **Owner-Operator** — Needs visibility, KPIs, cost insights, ability to delegate with confidence
2. **Kitchen Manager / Executive Chef** — Needs standardized recipes, inventory cross-referencing, training material that survives staff turnover
3. **Admin / Accountant** — Needs consolidated data exports, cost reports that explain WHY not just WHAT

## Validated Insights (as of April 2026)
- Problem validated qualitatively (~15 conversations)
- Solution validated (Victor Murguia, Anna Palazuelos)
- Price range validated: $1,000–$2,000 MXN/month per location (~$55–110 USD)
- The operational sequence is: standardization → inventory → cost interpretation (NOT the reverse)
- Framing as "augmentation, not replacement" increases adoption willingness
- Chef adopts, owner pays — two different narratives for chains

## MVP Learnings
The Gradio MVP (Python + Gradio + SQLite) validated:
- Bienvenida: Captures restaurant identity via conversational AI
- Clasificacion: Generates restaurant classification and description
- Configuracion: Sets up units, families, categories with consistency checks
- Alineamiento: Maps recipe ingredients to inventory items
- Estructura: Enriches inventory items with units, families, purchase factors
- Manual Operativo: Generates operational manual from structured data

Key learning: The AI-guided pipeline works. Operators provide messy data → AI proposes structured output → operator reviews and confirms.
</context>

<PRD>
# Product Requirements Document — Zenet Production Software v1.0

## 1. Product Vision

Build the production version of Zenet's standardization platform: a multi-tenant SaaS web application that guides restaurant operators from onboarding through full operational standardization, culminating in a living Manual Operativo with KPIs, AI insights, and operational dashboards.

**Timeline:** April 2026 — October 2026 (7 months)
**Total features:** 37 features across 7 development phases

---

## 2. Technical Architecture

### Stack

**Frontend:**
- Framework: Next.js 15+ (App Router)
- Language: TypeScript, React 19
- UI Components: shadcn/ui + Radix UI
- Styling: Tailwind CSS
- State Management: Zustand (client state), TanStack Query (server state)
- Forms: react-hook-form + zod
- Testing: vitest (unit), Playwright (E2E), axe-core (accessibility)

**Backend:**
- Framework: FastAPI (Python 3.13)
- Validation: Pydantic
- Rate Limiting: slowapi
- Package Manager: uv (never pip)
- Testing: pytest

**Database & Services:**
- Database: Supabase (managed PostgreSQL)
- Authentication: Supabase Auth (email/password, JWT)
- Multi-tenancy: Row-Level Security (RLS) per tenant
- AI: Anthropic Claude API (Sonnet 4.6 default, Opus 4.6 for complex reasoning)
- AI Monitoring: Langfuse
- File Storage: Supabase Storage (S3-compatible)
- Deployment (Frontend): Vercel
- Deployment (Backend): Railway

### Data Architecture (17 tables)

**Auth & Tenancy (3 tables):**
- `tenant` — Top-level business entity (id UUID, name, slug, plan, is_active)
- `profile` — Extends auth.users (full_name, avatar_url, phone)
- `tenant_member` — User-to-tenant junction with roles (owner, admin, chef, staff)

**Configuration (5 tables):**
- `restaurant` — Profile (name, type, address, city, state, phone, email, operating_hours JSONB, seating_capacity, logo_url)
- `recipe_unit` — Recipe measurement units (name, symbol, is_standard). Standard: g, kg, ml, L, pza
- `inventory_unit` — Inventory units with self-referential equivalence chain (name, symbol, base_unit_id, factor_to_base, is_standard). 1 caja = 10 kg = caja.base_unit_id → kg, factor=10
- `category_recipe` — Recipe categories (name, description, sort_order). E.g., Entradas, Platos Fuertes, Bebidas
- `family_inventory` — Inventory grouping (name, description, base_unit_id, sort_order). E.g., Carnes, Lacteos, Verduras

**Recipe & Inventory (3 tables):**
- `recipe` — Recipes (name, category_id FK, description, steps JSONB, servings, prep_time_min, cook_time_min, image_url, is_active)
- `recipe_ingredient` — Ingredients per recipe (recipe_id FK, name, quantity, unit_id FK → recipe_unit, inventory_item_id FK → inventory_item, sort_order)
- `inventory_item` — Dual-unit items (name, stock_unit_id FK, purchase_unit_id FK, purchase_to_stock_factor, category TEXT, family_id FK, min_stock_quantity, current_stock_quantity, cost_per_purchase_unit, supplier_name)

**Normalization (1 table):**
- `recipe_unit_conversion` — Context-sensitive conversions (recipe_unit_id FK, family_id FK nullable, inventory_item_id FK nullable, quantity, base_unit_id FK, source). Lookup priority: (unit, family, item) → (unit, family, NULL) → (unit, NULL, item) → (unit, NULL, NULL)

**Operations (3 tables):**
- `classification` — Structured restaurant classification (restaurant_type, description, key_characteristics JSONB, cuisine_types JSONB, service_style, confirmed_by_operator)
- `standardization_progress` — Per-section completion tracking (section, status, total_items, completed_items, completion_pct GENERATED)
- `deduction_log` — Historical inventory deductions (recipe_id, inventory_item_id, quantity_deducted, unit_id, servings, deducted_by, deducted_at)

**AI & Sessions (3 tables):**
- `conversation` — Per-section conversation (section, agent_type, status, metadata JSONB)
- `conversation_message` — Individual messages (conversation_id FK, role, content, tool_calls JSONB, tool_results JSONB, token_count)
- `agent_state` — Agent state per section (agent_type, state_data JSONB, version)

**Common columns on all tenant-scoped tables:**
- `tenant_id UUID NOT NULL REFERENCES tenant(id)`
- `created_at TIMESTAMPTZ DEFAULT now()`
- `updated_at TIMESTAMPTZ DEFAULT now()`
- `created_by UUID REFERENCES auth.users(id)`
- `deleted_at TIMESTAMPTZ` (soft delete)
- Unique constraints use `WHERE deleted_at IS NULL`

**Enumerations (application-level, not DB tables):**
- Restaurant types: Casual, Rapida, Gourmet, Cafeteria, Cafe
- Inventory categories: perishable, non_perishable
- Tenant member roles: owner, admin, chef, staff
- Sections: bienvenida, clasificacion, configuracion, alineamiento, estructura, normalizacion, manual_operativo
- Section status: not_started, in_progress, completed
- Message roles: user, assistant, system, tool

### AI Agent Architecture

8 agents, all extending BaseAgent:

| Agent | Section | Purpose |
|-------|---------|---------|
| OnboardingAgent | Bienvenida | Welcome, introduction, initial data capture |
| ClassificationAgent | Clasificacion | Restaurant type classification, description generation |
| ConfigurationAgent | Configuracion | Guide unit/family/category setup, consistency checks |
| ConsistencyCheckAgent | Configuracion | Validate configuration completeness |
| AlignmentAgent | Alineamiento | Recipe entry, ingredient-to-inventory mapping |
| StructuringAgent | Estructura | Inventory enrichment (units, families, factors) |
| NormalizationAgent | Normalizacion | Unit mismatch detection and resolution |
| InterpretationAgent | Manual Operativo | Data interpretation, KPI insights, operational Q&A |

**Agent conventions:**
- Default model: Claude Sonnet 4.6 (`claude-sonnet-4-6`)
- Complex reasoning: Claude Opus 4.6 (`claude-opus-4-6`)
- All user-facing text in Spanish
- All agents use tool-calling for structured operations
- Never make changes without operator confirmation
- Monitor all calls via Langfuse

### Multi-Tenancy & Security

- Every tenant-scoped table has `tenant_id UUID` column
- RLS policies enforce data isolation — users see only their tenant's data
- JWT from Supabase Auth contains `user_id`; policies join through `tenant_member`
- One tenant = one restaurant (v1)
- User roles: owner (full access + billing), admin (everything except billing), chef (recipes + inventory + manual operativo), staff (read-only manual operativo + KPIs)

### API Structure

All endpoints under `/api/v1/`:

**Authentication:**
- `POST /api/v1/auth/register` — Sign up
- `POST /api/v1/auth/login` — Login
- `POST /api/v1/auth/refresh` — Refresh token

**Restaurant:**
- `POST /api/v1/restaurants` — Create restaurant
- `GET /api/v1/restaurants/{id}` — Get restaurant profile
- `PATCH /api/v1/restaurants/{id}` — Update restaurant

**Standardization:**
- `POST /api/v1/standardization/{section}` — Submit section data
- `GET /api/v1/standardization/{section}` — Retrieve section data
- `PATCH /api/v1/standardization/{section}` — Update section

**Configuration entities (CRUD):**
- `/api/v1/recipe-units` — Recipe units
- `/api/v1/inventory-units` — Inventory units
- `/api/v1/category-recipes` — Recipe categories
- `/api/v1/family-inventories` — Inventory families
- `/api/v1/recipes` — Recipes with ingredients
- `/api/v1/inventory-items` — Inventory items

**Manual Operativo:**
- `GET /api/v1/manual-operativo/dashboard` — KPI dashboard
- `GET /api/v1/manual-operativo/dimensions` — Standardization dimensions
- `GET /api/v1/manual-operativo/suggestions` — AI-generated improvement suggestions

**AI Assistant:**
- `POST /api/v1/ai/chat` — Send message to assistant
- `POST /api/v1/ai/upload` — Upload file for processing
- `GET /api/v1/ai/history` — Retrieve conversation history

---

## 3. User Experience

### The Three Phases

| Phase | Name | Purpose | Duration |
|-------|------|---------|----------|
| 1 | Onboarding | Create account, set up restaurant profile, meet AI assistant | 5–10 min |
| 2 | Standardization | Structure recipes, inventory, units through 6 AI-guided sections | 2–4 hours |
| 3 | Manual Operativo | Living operational dashboard with KPIs and AI insights | Ongoing |

### Design Principles

1. **Operator-first language** — Every label uses the operator's language, not technical jargon
2. **Progressive disclosure** — Show only what's relevant at each step
3. **Always show progress** — Operator always knows where they are, what's complete, what's next
4. **AI as companion, not gatekeeper** — Always available, never mandatory
5. **Smooth, practical experience** — If the operator feels like they're fighting the software, we've failed

### Phase 1 — Onboarding

**User journey:** Landing Page → Sign Up → Restaurant Profile → AI Welcome → Dashboard

**Sign Up:**
- Email + password via Supabase Auth
- Basic personal info: Name, role (Owner, Manager, Chef)
- No credit card required

**Restaurant Profile:**
- Restaurant name (required)
- Restaurant type — Casual, Rapida, Gourmet, Cafeteria, Cafe (required)
- Address, city, state (required — at least one)
- Cuisine type, years in operation, current tools (optional)
- Logo/photo (optional)

**AI Welcome:**
- AI assistant appears in persistent sidebar
- Introduces itself and explains the process
- Asks probing questions about the restaurant

**Behind the scenes:**
- Restaurant entity created
- Default units, families, categories pre-loaded based on restaurant type
- AI has full context for all future conversations

### Phase 2 — Standardization (6 Sections)

**Layout:** Dashboard with section cards showing status (Not started / In progress / Complete), completion percentage, and "Continue" / "Start" button. Overall standardization score displayed.

Each section has a two-column layout:
- **Left column:** AI chat assistant (persistent sidebar)
- **Right column:** Data tables, forms, and progress visualization

**Three input modes (all sections):**
1. **Upload** — PDF, Excel, photos → AI extracts and proposes structured data
2. **Conversation** — Natural language chat with the AI agent
3. **Manual** — Direct editing of tables and forms

#### Section 1: Clasificacion
- AI generates restaurant classification from onboarding data
- Operator reviews and adjusts
- AI generates narrative description
- Output: Classification record used by all subsequent sections

#### Section 2: Configuracion
- Set up recipe categories (Entradas, Platos Fuertes, Bebidas, etc.)
- Set up inventory families (Carnes, Lacteos, Verduras, etc.)
- Define recipe units (cucharada, porcion, taza, etc.)
- Define inventory units (kg, caja, bolsa) with equivalence chains
- System pre-loads defaults based on restaurant type
- AI runs consistency checks
- Progress dashboard shows what's configured vs. pending

#### Section 3: Alineamiento
- Enter recipes one by one (name, category, ingredients, quantities, units)
- AI extracts ingredients from uploaded files (menus, recipe cards, photos)
- AI proposes matching inventory items for each ingredient
- Operator confirms, adjusts, or creates new inventory items
- Editable recipe table with completion progress

#### Section 4: Estructura
- Enrich each inventory item: stock unit, purchase unit, conversion factor, family, category
- AI proposes enrichment based on restaurant type and industry patterns
- Two-phase flow: Perecederos first, then No Perecederos
- Editable inventory table with all structured fields
- Missing units/families created on the fly

#### Section 5: Normalizacion
- Detect unit mismatches between recipe units and inventory units
- Per-recipe table showing ingredients with difference warnings
- Operator resolves mismatches via chat with the AI agent (set conversion factor, change unit)
- All recipes validated as ready for deduction

#### Section 6: Review & Confirm
- Operator reviews each section's output before advancing
- Confirm button saves and locks section
- Phase transitions with greeting messages

### Phase 3 — Manual Operativo

**Purpose:** Transform structured data into a living operational dashboard.

**Tabs:**

1. **KPI Dashboard**
   - Overall standardization score (%)
   - Standardization by dimension (Recipes, Inventory, Units, Families)
   - Number of standardized recipes vs. total
   - Number of fully structured inventory items vs. total
   - Consistency score from Normalizacion validation

2. **Standardization Dimensions**
   - Visual breakdown per dimension with progress indicators
   - Areas needing attention highlighted

3. **Improvement Areas**
   - AI-generated insights and actionable recommendations
   - Priority ordering based on impact

4. **Data Visualization**
   - Restaurant profile, users, recipes, inventory, normalizations
   - All data viewable in organized tabs

5. **AI Assistant (Interpretation Mode)**
   - Shifts from guide mode to interpretation mode
   - Helps understand what numbers mean
   - Suggests priorities
   - Answers operational questions

6. **Admin Panel**
   - Software configuration
   - User/team management
   - Account settings

### AI Assistant — Persistent Companion

The AI assistant is a persistent sidebar available across all phases:

**During Standardization (Guide Mode):**
- Guides operator through each section
- Processes file uploads
- Proposes structured data from natural language
- Detects gaps and asks clarifying questions
- Never makes changes without confirmation

**During Manual Operativo (Interpretation Mode):**
- Interprets KPIs and operational data
- Suggests priorities and improvement actions
- Answers operational questions about the restaurant's data
- Explains deviations and cost implications

---

## 4. Development Phases

### Month 1: Foundation (April 2026)

**Goal:** Infrastructure ready. Nothing visible to users yet.

| ID | Feature | Description | Complexity |
|----|---------|-------------|------------|
| F0.1 | Supabase schema | All 17 tables, RLS policies, seed data | High |
| F0.2 | API scaffolding | FastAPI project, route structure, middleware, auth | Medium |
| F0.3 | Frontend scaffolding | Next.js project, layout, routing, shadcn/ui setup | Medium |
| F0.4 | Deployment pipeline | Vercel + Railway connected to main branch | Medium |
| F0.5 | Environment setup | .env management, API keys, Supabase connection | Low |
| F0.6 | AI infrastructure | Claude provider, prompt templates, Langfuse monitoring | Medium |

**Success criteria:** Infrastructure deployed, empty app accessible online, API health check works, CI runs tests.

### Month 2: Onboarding (May 2026)

**Goal:** A restaurant can sign up, be greeted by AI, fill profile, and get classified.

| ID | Feature | Description | Complexity |
|----|---------|-------------|------------|
| F1.1 | Authentication | Email/password sign up & login via Supabase Auth | Medium |
| F1.2 | Bienvenida | Welcome screen, AI-guided introduction | Low |
| F1.3 | AI Assistant infrastructure | Persistent sidebar chat, conversation memory, tool-calling | High |
| F1.4 | Profile & business info | Restaurant name, type, address, contact | Medium |
| F1.5 | Clasificacion | AI classifies restaurant, generates description, operator confirms | High |

**Dependencies:** F1.1 blocks all others. F1.3 is reused by all subsequent sections.
**Success criteria:** Operator can sign up, get classified, see profile. Session persists.

### Month 3: Configuracion (June 2026)

**Goal:** Recipe structure fully defined — categories, families, units configured.

| ID | Feature | Description | Complexity |
|----|---------|-------------|------------|
| F2.1 | Configuracion agent | AI chat for guided configuration | High |
| F2.2 | Recipe categories | Create/edit recipe categories | Medium |
| F2.3 | Inventory families | Create/edit inventory families | Medium |
| F2.4 | Recipe units | Define recipe measurement units | Medium |
| F2.5 | Inventory units | Define inventory units with equivalence chains | Medium |
| F2.6 | Progress visualization | Dashboard showing configuration completeness | Medium |
| F2.7 | Multi-input mode | Manual, chat, file upload (PDF/Excel/images) | High |

**Dependencies:** F2.1 depends on F1.3. F2.7 is shared by Alineamiento and Estructura.
**Success criteria:** All categories, families, and units configured and saved.

### Month 4: Alineamiento (July 2026)

**Goal:** All recipes entered, ingredients linked to inventory items.

| ID | Feature | Description | Complexity |
|----|---------|-------------|------------|
| F3.1 | Alineamiento agent | AI chat for recipe-by-recipe data entry | High |
| F3.2 | Recipe input | Enter recipes with ingredients, quantities, units | High |
| F3.3 | Multi-input mode | Manual, chat, file upload (menus, recipe cards, photos) | High |
| F3.4 | Ingredient-to-inventory linking | AI proposes inventory item mappings | High |
| F3.5 | Tables & progress view | Editable recipe table, completion tracking | Medium |

**Dependencies:** F3.2 depends on Configuracion data (categories, units).
**Success criteria:** All recipes entered with ingredients linked to inventory.

### Month 5: Estructura (August 2026)

**Goal:** Every inventory item fully structured with units, families, conversion factors.

| ID | Feature | Description | Complexity |
|----|---------|-------------|------------|
| F4.1 | Estructura agent | AI chat for inventory structuring | High |
| F4.2 | Inventory structuring | Enrich items: stock/purchase units, factors, families | High |
| F4.3 | Multi-input mode | Manual, chat, file upload (supplier lists, invoices) | High |
| F4.4 | Tables & progress view | Editable inventory table, completion tracking | Medium |
| F4.5 | Perecedero/No perecedero flow | Two-phase processing | Medium |

**Dependencies:** F4.2 depends on inventory shells from Alineamiento.
**Success criteria:** All items enriched with units, families, factors.

### Month 6: Normalizacion (September 2026)

**Goal:** All unit mismatches detected and resolved. Recipes ready for deduction.

| ID | Feature | Description | Complexity |
|----|---------|-------------|------------|
| F5.1 | Normalizacion agent | AI chat for resolving unit mismatches | Medium |
| F5.2 | Per-recipe normalization table | Table with items flagged for unit mismatches | Medium |
| F5.3 | Chat-based resolution | Resolve mismatches via conversation with agent | Medium |

**Dependencies:** F5.2 depends on complete recipe data (Month 4) and structured inventory (Month 5).
**Success criteria:** All unit mismatches resolved. All recipes ready for deduction.

### Month 7: Manual Operativo (October 2026)

**Goal:** Living operational manual with KPIs, AI insights, and data visualization.

| ID | Feature | Description | Complexity |
|----|---------|-------------|------------|
| F6.1 | KPIs dashboard | Readiness report, standardization scores, completeness | High |
| F6.2 | Standardization dimensions | Visual breakdown per dimension | Medium |
| F6.3 | Improvement areas | AI-identified gaps and recommendations | Medium |
| F6.4 | AI assistant chat | Persistent AI for operational questions (interpretation mode) | High |
| F6.5 | Data visualization | Views for restaurant, recipes, inventory, normalizations | High |
| F6.6 | Admin panel | Software configuration, user management, account settings | Medium |

**Dependencies:** F6.1–F6.3 depend on complete standardization data (Months 3–6).
**Success criteria:** KPI dashboard live, AI chat working, all data viewable. Platform ready for beta.

---

## 5. Shared Components (Built Once, Reused)

| Component | Used by | Built in |
|-----------|---------|----------|
| AI Assistant sidebar | All sections | Month 2 (F1.3) |
| Multi-input mode (manual/chat/file) | Configuracion, Alineamiento, Estructura | Month 3 (F2.7) |
| Editable data table | Configuracion, Alineamiento, Estructura, Normalizacion, Manual Operativo | Month 3 (F2.6) |
| Progress visualization | All standardization sections | Month 3 (F2.6) |
| File upload + extraction | Configuracion, Alineamiento, Estructura | Month 3 (F2.7) |
| Difference/warning indicators | Normalizacion, Manual Operativo KPIs | Month 6 (F5.2) |

---

## 6. Cross-Cutting Concerns (Continuous)

| Area | Activities |
|------|-----------|
| Testing | Unit tests per feature, integration tests per section, E2E for critical flows |
| Security | RLS policies, input validation, API auth middleware, rate limiting, CORS |
| Performance | Query optimization, caching, lazy loading, bundle size |
| AI/Prompts | Prompt engineering, token optimization, response quality tuning, Langfuse monitoring |
| UX Polish | Responsive design, loading states, error messages, accessibility |
| Bug Fixes | Continuous triage and resolution |

---

## 7. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| AI prompt quality across sections | Features feel broken if AI responses are poor | Invest in prompt engineering early; test with real restaurant data |
| Month 3–5 are all high-complexity | Schedule pressure accumulates | Multi-input mode is shared; build once in Month 3 |
| Solo developer bottleneck | No parallelization possible | Prioritize ruthlessly; cut scope before quality |
| File upload/extraction reliability | PDFs and images are messy | Vision models for images; accept imperfect extraction with human review |
| Supabase RLS complexity | Security gaps or query performance | Design RLS policies upfront in Month 1; test thoroughly |
| Name-based → FK migration | Ingredient linking changes from name-based (MVP) to UUID FK (production) | Design schema with FKs from day 1; no migration needed |

---

## 8. Success Criteria

| Milestone | Criteria |
|-----------|---------|
| Month 1 | Infrastructure deployed, empty app accessible online |
| Month 2 | A restaurant can sign up, get classified, and see their profile |
| Month 3 | Recipe structure fully configured (categories, families, units) |
| Month 4 | All recipes entered with ingredients linked to inventory |
| Month 5 | All inventory items fully structured with units and conversions |
| Month 6 | All unit mismatches detected and resolved; recipes ready for deduction |
| Month 7 | Manual Operativo live with KPIs, AI chat, and data visualization |
| **Launch ready** | **One restaurant has completed the full flow end-to-end** |

---

## 9. Out of Scope (v1.0)

- Multi-location support (v2)
- Mobile app (v2)
- POS integrations (v2)
- Forecasting module (v2)
- Supply chain optimization (v2)
- Advanced analytics (v2)
- Google/Apple sign-in (can add post-launch)
- Inventory purchase tracking / full transaction ledger (post-launch)
- Recipe versioning / change history (post-launch)
- Supplier management as separate entity (post-launch)

---

## 10. Project Structure

```
zenet/
├── CLAUDE.md                          # Claude Code instructions
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
│   │   ├── (auth)/                    # Login, register
│   │   └── (dashboard)/              # Authenticated routes
│   │       ├── onboarding/
│   │       ├── standardization/      # 6 section pages
│   │       ├── manual-operativo/     # KPIs, dimensions, suggestions
│   │       └── settings/
│   ├── src/components/               # ui/, layout/, chat/, standardization/, manual-operativo/
│   ├── src/hooks/                    # use-auth, use-restaurant, use-chat, use-standardization
│   ├── src/lib/                      # supabase/, api.ts, utils.ts, constants.ts
│   ├── src/stores/                   # Zustand: auth, restaurant, chat
│   ├── src/types/                    # TypeScript type definitions
│   └── tests/                        # vitest + Playwright
│
├── backend/                          # FastAPI application
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/v1/                   # auth, restaurants, standardization, manual_operativo, ai
│   │   ├── models/                   # Pydantic models
│   │   ├── schemas/                  # Request/response schemas
│   │   ├── services/                 # Business logic
│   │   ├── agents/                   # 8 AI agents (base + 7 specialized + consistency check)
│   │   ├── core/                     # normalization, readiness, taxonomy
│   │   └── middleware/               # auth, rate_limit
│   └── tests/                        # pytest
│
└── supabase/                         # Supabase configuration
    ├── migrations/                   # SQL migrations
    ├── seed.sql                      # Standard units, templates per restaurant type
    └── config.toml
```

---

## 11. Key Constraints

- **No ORM** — Use Supabase client, not SQLAlchemy
- **uv over pip** — Always use `uv add` / `uv sync` for Python
- **All IDs are UUIDs** — Never sequential integers
- **All user-facing text in Spanish** — Code and comments in English
- **API keys in .env only** — Never hardcode credentials
- **Soft deletes only** — Never hard delete user data
- **AI never acts without confirmation** — Always propose, never auto-apply
- **shadcn/ui components are auto-generated** — Do not manually edit `components/ui/`
- **Git workflow: GitHub Flow** — main + feature/* + bugfix/*, never commit to main directly

---

## 12. Reference Documents

| Document | Description |
|----------|-------------|
| `docs/business-context.md` | Problem, solution, market, personas, value proposition, validation |
| `docs/core-user-experience.md` | Three-phase UX flow, AI assistant behavior, design principles |
| `docs/feature-roadmap.md` | 37 features across 7 months, dependencies, success criteria |
| `docs/data-model-overview.md` | 17 tables, relationships, RLS policies, migration strategy |
| `docs/api-design.md` | Endpoint conventions, versioning, error handling |

</PRD>
