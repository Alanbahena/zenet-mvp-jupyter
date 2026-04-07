# Zenet Production Software — Feature Roadmap v1

## Vision

Build the production version of Zenet's standardization platform: a web application that guides restaurant operators from onboarding through full operational standardization, culminating in a living Manual Operativo.

## Scope

This roadmap covers the **standardization phase** of Zenet — the first product a restaurant interacts with. It transforms a restaurant's informal operations into a structured, measurable system.

## Timeline

**Start:** April 2026
**Target completion:** September–October 2026 (6–7 months)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Zenet Platform                        │
│                                                         │
│  Phase 1: Onboarding                                    │
│  ┌─────────┐ ┌───────────┐ ┌──────────┐ ┌───────────┐  │
│  │  Auth   │ │Bienvenida │ │  Perfil  │ │Clasificac.│  │
│  └─────────┘ └───────────┘ └──────────┘ └───────────┘  │
│                                                         │
│  Phase 2: Standardization                               │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────────────┐ │
│  │Configurac. │ │Alineamiento│ │ Estructura │ │Normalizacion  │ │
│  │(Recetario) │ │ (Recetas)  │ │(Inventario)│ │(Equivalencias)│ │
│  └────────────┘ └────────────┘ └────────────┘ └───────────────┘ │
│                                                         │
│  Phase 3: Manual Operativo                              │
│  ┌────────────────────────────────────────────────────┐  │
│  │  KPIs · Dimensiones · Mejoras · AI Chat · Admin   │  │
│  └────────────────────────────────────────────────────┘  │
│                                                         │
│  ┌────────────────────────────────────────────────────┐  │
│  │          AI Assistant (persistent sidebar)         │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Visual Timeline

```
APR 2026       MAY            JUN            JUL            AUG            SEP            OCT
┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬
│              │              │              │              │              │              │              │
│  FOUNDATION  │  ONBOARDING  │CONFIGURACION │ ALINEAMIENTO │  ESTRUCTURA  │NORMALIZACION │MANUAL OPERAT.│
│              │              │              │              │              │              │              │
│ ▪ Supabase   │ ▪ Auth flow  │ ▪ Config     │ ▪ Recipe     │ ▪ Inventory  │ ▪ Normaliz.  │ ▪ KPIs       │
│   schema     │ ▪ Bienvenida │   agent      │   agent      │   agent      │   agent      │ ▪ Dimensions │
│ ▪ API        │ ▪ AI assist  │ ▪ Categories │ ▪ Recipe-by- │ ▪ Inventory  │ ▪ Difference │ ▪ Improvement│
│   scaffold   │   infra      │ ▪ Families   │   recipe     │   structuring│   warnings   │   areas      │
│ ▪ Frontend   │ ▪ Profile &  │ ▪ Units      │   input      │ ▪ Multi-     │ ▪ Per-recipe │ ▪ AI chat    │
│   scaffold   │   business   │ ▪ Progress   │ ▪ Tables &   │   input mode │   normaliz.  │ ▪ Data views │
│ ▪ Deploy     │   info       │   views      │   progress   │ ▪ Tables &   │   table      │ ▪ Admin      │
│   pipeline   │ ▪ Clasifica- │ ▪ Multi-     │ ▪ File       │   progress   │ ▪ Chat-based │   panel      │
│ ▪ CI/CD      │   cion       │   input mode │   upload     │              │   resolution │              │
│              │              │              │              │              │              │  ── LAUNCH ──│
├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│   MONTH 1    │   MONTH 2    │   MONTH 3    │   MONTH 4    │   MONTH 5    │   MONTH 6    │    MONTH 7   │
└──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘

Cross-cutting concerns (continuous):
──────────────────────────────────────────────────────────────────────────────────────────
  Testing · Security · Performance · AI prompt engineering · UX polish · Bug fixes
──────────────────────────────────────────────────────────────────────────────────────────
```

---

## Month 1: Foundation (April 2026)

**Goal:** Infrastructure ready. Nothing visible to users yet, but everything needed to build fast.

### Features

| # | Feature | Description | Complexity |
|---|---------|-------------|------------|
| F0.1 | Supabase schema | All tables, RLS policies, seed data | High |
| F0.2 | API scaffolding | FastAPI project, route structure, middleware | Medium |
| F0.3 | Frontend scaffolding | Next.js project, layout, routing, component library setup | Medium |
| F0.4 | Deployment pipeline | Vercel (frontend) + Railway (backend) connected to main branch | Medium |
| F0.5 | Environment setup | .env management, API keys, Supabase connection | Low |
| F0.6 | AI infrastructure | Claude provider, prompt templates, Langfuse monitoring | Medium |

### Deliverables
- [ ] Database schema deployed to Supabase (dev environment)
- [ ] API responds to health check at `/api/v1/health`
- [ ] Frontend renders empty shell at deployed URL
- [ ] CI runs tests on every PR
- [ ] AI provider can make a basic Claude call

---

## Month 2: Onboarding (May 2026)

**Goal:** A restaurant can sign up, be greeted by the AI assistant, fill in their profile, and get classified.

### Features

| # | Feature | Description | Complexity |
|---|---------|-------------|------------|
| F1.1 | Authentication | Email/password sign up & login via Supabase Auth | Medium |
| F1.2 | Bienvenida | Welcome screen, AI-guided introduction to Zenet | Low |
| F1.3 | AI Assistant infrastructure | Persistent sidebar chat component, conversation memory, tool-calling framework | High |
| F1.4 | Profile & business info | Restaurant name, type, location, contact, operator role | Medium |
| F1.5 | Clasificacion | AI agent classifies restaurant type, generates description, confirms with operator | High |

### Dependencies
- F1.1 blocks all other features (user must exist first)
- F1.3 is used by F1.5 and all subsequent agent-based sections
- F1.4 feeds data into F1.5 (classification needs restaurant context)

### Deliverables
- [ ] Operator can create account and log in
- [ ] AI assistant greets operator and explains the process
- [ ] Restaurant profile saved to database
- [ ] Classification completed and stored
- [ ] Session persists across browser refreshes

---

## Month 3: Configuracion (June 2026)

**Goal:** Restaurant's recipe structure is defined — categories, families, and units are configured.

### Features

| # | Feature | Description | Complexity |
|---|---------|-------------|------------|
| F2.1 | Configuracion agent | AI chat agent that guides operator through recipe/inventory configuration | High |
| F2.2 | Categorias de recetas | Create/edit recipe categories (Entradas, Platos fuertes, Bebidas, etc.) | Medium |
| F2.3 | Familias de inventario | Create/edit inventory families (Carnes, Lacteos, Verduras, etc.) | Medium |
| F2.4 | Unidades de receta | Define recipe units (porcion, plato, vaso, etc.) | Medium |
| F2.5 | Unidades de inventario | Define inventory units (kg, L, pza, caja, etc.) with equivalences | Medium |
| F2.6 | Progress visualization | Dashboard showing configuration completeness, missing items, readiness | Medium |
| F2.7 | Multi-input mode | Manual entry, conversational (chat), file upload (PDF/Excel/images) | High |

### Dependencies
- F2.1 depends on AI Assistant infrastructure (F1.3)
- F2.2–F2.5 are independent of each other but all feed into F2.6
- F2.7 is a shared capability used by Alineamiento and Estructura too

### Deliverables
- [ ] Operator can configure all recipe categories via chat or manual entry
- [ ] Inventory families defined and stored
- [ ] Recipe and inventory units with equivalences saved
- [ ] Progress dashboard shows what's configured vs. pending
- [ ] File upload extracts and processes configuration data

---

## Month 4: Alineamiento / Recetario (July 2026)

**Goal:** All recipes entered, ingredient by ingredient, linked to inventory items.

### Features

| # | Feature | Description | Complexity |
|---|---------|-------------|------------|
| F3.1 | Alineamiento agent | AI chat agent for recipe-by-recipe data entry and alignment | High |
| F3.2 | Recipe input (per recipe) | Operator enters each recipe with name, category, ingredients, quantities, units | High |
| F3.3 | Multi-input mode | Manual form, conversational chat, file upload (menus, recipe cards, photos) | High |
| F3.4 | Ingredient-to-inventory linking | AI proposes which inventory item each ingredient maps to | High |
| F3.5 | Tables & progress view | Editable recipe table, completion progress, missing ingredients highlighted | Medium |

### Dependencies
- F3.1 depends on AI Assistant infrastructure (F1.3)
- F3.2 depends on Configuracion data (categories, units) from Month 3
- F3.4 depends on inventory items (shells created here, enriched in Estructura)

### Deliverables
- [ ] Operator can enter recipes via chat, form, or file upload
- [ ] Each recipe linked to its category and ingredients
- [ ] AI suggests inventory item mappings for each ingredient
- [ ] Recipe table is editable and shows real-time progress
- [ ] All recipes saved and ready for Estructura phase

---

## Month 5: Estructura / Inventarios (August 2026)

**Goal:** Every inventory item is fully structured — units, families, categories, conversion factors.

### Features

| # | Feature | Description | Complexity |
|---|---------|-------------|------------|
| F4.1 | Estructura agent | AI chat agent for inventory structuring and enrichment | High |
| F4.2 | Inventory structuring | Enrich each item: stock unit, purchase unit, conversion factor, family, category | High |
| F4.3 | Multi-input mode | Manual edit, conversational, file upload (supplier lists, invoices) | High |
| F4.4 | Tables & progress view | Editable inventory table with all structured fields, completion tracking | Medium |
| F4.5 | Perecedero/No perecedero flow | Two-phase flow: perishables first, then non-perishables | Medium |

### Dependencies
- F4.1 depends on AI Assistant infrastructure (F1.3)
- F4.2 depends on inventory item shells from Alineamiento (Month 4)
- F4.5 depends on inventory categories from Configuracion (Month 3)

### Deliverables
- [ ] All inventory items enriched with units, families, conversion factors
- [ ] Perecederos and No Perecederos processed in sequence
- [ ] Operator can edit any item in the table before confirming
- [ ] Missing units/families created on the fly when needed
- [ ] Inventory fully structured and ready for Manual Operativo

---

## Month 6: Normalizacion (September 2026)

**Goal:** Detect and resolve unit mismatches between recipe units and inventory units — ensure every recipe ingredient can be correctly deducted from inventory.

### Features

| # | Feature | Description | Complexity |
|---|---------|-------------|------------|
| F5.1 | Normalizacion agent | AI chat agent that helps resolve unit differences between recipes and inventory | Medium |
| F5.2 | Per-recipe normalization table | Table showing each recipe with its ingredients, highlighting items with unit mismatches (difference warnings) | Medium |
| F5.3 | Chat-based resolution | Operator can select a flagged item and resolve the mismatch through conversation with the agent (set conversion factor, change unit, etc.) | Medium |

### Dependencies
- F5.1 depends on AI Assistant infrastructure (F1.3)
- F5.2 depends on complete recipe data (Month 4) and structured inventory (Month 5)
- F5.3 depends on F5.1 and F5.2

### Deliverables
- [ ] Normalization table shows all recipes with ingredient-to-inventory unit mappings
- [ ] Mismatched items highlighted with difference warnings
- [ ] Operator can resolve mismatches via chat with the agent
- [ ] Resolved normalizations saved and reflected in the table
- [ ] All recipes ready for deduction (no unresolved unit mismatches)

---

## Month 7: Manual Operativo (October 2026)

**Goal:** The restaurant has a living operational manual — KPIs, dimensions, improvement areas, and an AI assistant for daily operations.

### Features

| # | Feature | Description | Complexity |
|---|---------|-------------|------------|
| F6.1 | KPIs dashboard | Readiness report, standardization score, completeness metrics | High |
| F6.2 | Standardization dimensions | Visual breakdown of each dimension (recipes, inventory, units, families) | Medium |
| F6.3 | Improvement areas | AI-identified gaps and actionable recommendations | Medium |
| F6.4 | AI assistant chat | Persistent AI chat that can query all restaurant data and answer operational questions | High |
| F6.5 | Data visualization | Views for: restaurant profile, users, recipes, inventory, normalizations | High |
| F6.6 | Admin panel | Software configuration, user management, account settings | Medium |

### Dependencies
- F6.1–F6.3 depend on complete standardization data (Months 3–6)
- F6.4 depends on AI Assistant infrastructure (F1.3) + all stored data
- F6.6 is independent and can be built in parallel

### Deliverables
- [ ] KPI dashboard shows real-time standardization metrics
- [ ] Each dimension visualized with progress and gaps
- [ ] AI assistant can answer questions about the restaurant's data
- [ ] All data viewable in organized tabs (restaurant, recipes, inventory, etc.)
- [ ] Admin panel for account and software configuration
- [ ] Platform ready for beta users

---

## Cross-Cutting Concerns (Continuous)

These are worked on throughout the entire timeline, not in a single month:

| Area | Activities |
|------|-----------|
| **Testing** | Unit tests per feature, integration tests per section, E2E for critical flows |
| **Security** | RLS policies, input validation, API auth middleware, rate limiting |
| **Performance** | Query optimization, caching, lazy loading, bundle size |
| **AI/Prompts** | Prompt engineering, token optimization, response quality tuning, Langfuse monitoring |
| **UX Polish** | Responsive design, loading states, error messages, accessibility basics |
| **Bug Fixes** | Continuous triage and resolution |

---

## Shared Components (Built Once, Used Everywhere)

These components are shared across multiple sections:

| Component | Used by | Built in |
|-----------|---------|----------|
| AI Assistant sidebar | All sections | Month 2 (F1.3) |
| Multi-input mode (manual/chat/file) | Configuracion, Alineamiento, Estructura | Month 3 (F2.7) |
| Editable data table | Configuracion, Alineamiento, Estructura, Normalizacion, Manual Operativo | Month 3 (F2.6) |
| Progress visualization | All standardization sections | Month 3 (F2.6) |
| File upload + extraction | Configuracion, Alineamiento, Estructura | Month 3 (F2.7) |
| Difference/warning indicators | Normalizacion, Manual Operativo (KPIs) | Month 6 (F5.2) |

---

## Feature Summary

| Phase | Features | Month |
|-------|----------|-------|
| Foundation | 6 infrastructure features | April |
| Onboarding | 5 features (auth, welcome, AI, profile, classification) | May |
| Configuracion | 7 features (agent, categories, families, units x2, progress, multi-input) | June |
| Alineamiento | 5 features (agent, recipe input, multi-input, linking, tables) | July |
| Estructura | 5 features (agent, structuring, multi-input, tables, two-phase flow) | August |
| Normalizacion | 3 features (agent, per-recipe table with warnings, chat resolution) | September |
| Manual Operativo | 6 features (KPIs, dimensions, improvements, AI chat, data views, admin) | October |
| **Total** | **37 features** | **7 months** |

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| AI prompt quality across sections | Features feel broken if AI responses are poor | Invest in prompt engineering early; test with real restaurant data |
| Month 3–5 are all high-complexity | Schedule pressure accumulates | Multi-input mode is shared; build it well once in Month 3 |
| Solo developer bottleneck | No parallelization possible | Prioritize ruthlessly; cut scope before cutting quality |
| File upload/extraction reliability | PDFs and images are messy | Use vision models for images; accept imperfect extraction with human review |
| Supabase RLS complexity | Security gaps or query performance | Design RLS policies upfront in Month 1; test thoroughly |

---

## Success Criteria

| Milestone | Criteria |
|-----------|---------|
| Month 1 complete | Infrastructure deployed, empty app accessible online |
| Month 2 complete | A restaurant can sign up, get classified, and see their profile |
| Month 3 complete | Recipe structure fully configured (categories, families, units) |
| Month 4 complete | All recipes entered with ingredients linked to inventory |
| Month 5 complete | All inventory items fully structured with units and conversions |
| Month 6 complete | All unit mismatches detected and resolved; recipes ready for deduction |
| Month 7 complete | Manual Operativo live with KPIs, AI chat, and data visualization |
| **Launch ready** | **One restaurant has completed the full flow end-to-end** |
