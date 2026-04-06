# Zenet — Core User Experience (Production Software v1.0)

**Version:** v1.0 Draft
**Last Updated:** April 6, 2026
**Author:** Alan Bahena
**Purpose:** Define the end-to-end user experience for the first production release of Zenet, focused entirely on restaurant standardization.

---

## Table of Contents

1. [Experience Overview](#1-experience-overview)
2. [Design Principles](#2-design-principles)
3. [Phase 1 — Onboarding](#3-phase-1--onboarding)
4. [Phase 2 — Standardization](#4-phase-2--standardization)
5. [Phase 3 — Manual Operativo](#5-phase-3--manual-operativo)
6. [The Living Cycle](#6-the-living-cycle)
7. [AI Assistant — Persistent Companion](#7-ai-assistant--persistent-companion)
8. [User Flows by Persona](#8-user-flows-by-persona)
9. [Information Architecture](#9-information-architecture)
10. [Key Screens Summary](#10-key-screens-summary)
11. [Open Questions](#11-open-questions)

---

## 1. Experience Overview

### Core Premise

The first production release of Zenet is focused **entirely on restaurant standardization**. The product takes an operator from zero structure to a living operational manual — guided by AI every step of the way.

### The Three Phases

The user experience follows a clear, sequential journey:

| Phase | Name | Purpose |
|---|---|---|
| **1** | **Onboarding** | Create account, set up restaurant profile, meet the AI assistant |
| **2** | **Standardization** | Fill 5 sections that structure the restaurant's operational foundation |
| **3** | **Manual Operativo** | See the living result — KPIs, dimensions, improvement areas, AI insights |

### The Key Insight

This is not a form-filling experience. It's a **guided conversation** where the AI assistant helps the operator translate their messy, real-world knowledge into clean, structured operational data. The operator can work through each section either by:

- **Uploading existing data** (Excel files, photos of recipes, PDFs)
- **Conversing with the AI agent** (natural language, Q&A)
- **Manual entry** (direct editing of tables and forms)

All three methods lead to the same structured output.

---

## 2. Design Principles

### 2.1 Operator-First Language

Every label, instruction, and message uses the operator's language — not technical jargon. If the system needs to explain a concept (like "normalization"), it does so in practical terms the operator already understands.

**Example:**
- Don't say: "Configure inventory unit equivalences"
- Say: "Define how your purchase units convert to stock units (e.g., 1 box = 24 pieces)"

### 2.2 Progressive Disclosure

Show only what's relevant at each step. Don't overwhelm the operator with all 5 standardization sections at once. Guide them through the natural sequence, unlocking each section as the previous one provides the necessary data.

### 2.3 Always Show Progress

The operator should always know:
- Where they are in the process
- How much is complete
- What's next
- How their Manual Operativo is being built in real-time

### 2.4 AI as Companion, Not Gatekeeper

The AI assistant is always available but never mandatory. The operator can:
- Ask for help at any moment
- Ignore the assistant and work manually
- Switch between conversation and direct editing freely

### 2.5 Smooth, Practical Experience

The product must feel effortless. If the operator feels like they're fighting the software, we've failed. Every interaction should feel like it's saving them time, not costing it.

---

## 3. Phase 1 — Onboarding

### Purpose

Create the operator's account, capture the restaurant's identity, and introduce Zenet as a tool that will help standardize their operation.

### User Journey

```
Landing Page → Sign Up → Restaurant Profile → AI Welcome → Dashboard
```

### 3.1 Sign Up / Account Creation

**What happens:**
- Email + password (or Google/Apple sign-in via Supabase Auth)
- Basic personal info: Name, role (Owner, Manager, Chef)
- Accept terms of service

**Design notes:**
- Minimal friction — 3 fields max on the first screen
- No credit card required at this stage

### 3.2 Restaurant Profile Setup

**What the operator fills in:**

| Field | Required | Notes |
|---|---|---|
| Restaurant name | Yes | |
| Number of locations | Yes | 1-5 for v1 |
| Location addresses | Yes (at least 1) | Can add more later |
| Cuisine type | Yes | Dropdown with common types + "Other" |
| Years in operation | No | Helps AI contextualize advice |
| Current tools used | No | POS name, Excel, etc. — helps AI understand starting point |
| Logo / photo | No | Branding for the Manual Operativo |

**AI assistant role during onboarding:**
- Appears as a sidebar chat after account creation
- Introduces itself: "Soy tu asistente Zenet. Voy a ayudarte a estandarizar la operacion de tu restaurante paso a paso."
- Answers questions about what Zenet is, how it works, what to expect
- Asks probing questions to understand the restaurant better: "Cuantas recetas manejas aproximadamente?", "Como llevas tu inventario actualmente?"
- Uses this information to pre-configure defaults and tailor the standardization flow

### 3.3 Onboarding Complete → Dashboard

**What the operator sees:**
- Welcome message with their restaurant name
- A clear visual of the 3 phases (Onboarding ✓, Standardization, Manual Operativo)
- An invitation to start the first standardization section
- The AI assistant available in a persistent sidebar

**What happened behind the scenes:**
- Restaurant entity created in database
- Default units, families, and categories pre-loaded based on cuisine type
- AI assistant has context about the restaurant for all future conversations

---

## 4. Phase 2 — Standardization

### Purpose

Guide the operator through 5 sections that progressively build the restaurant's operational foundation. Each section structures a different dimension of the operation.

### The 5 Standardization Sections

| Order | Section | What it structures | Depends on |
|---|---|---|---|
| 1 | **Clasificacion** | Restaurant type, description, operational profile | Onboarding data |
| 2 | **Configuracion** | Units (kg, L, pza, box), families (Lacteos, Carnes), categories (Perecedero, No perecedero) | Clasificacion |
| 3 | **Alineamiento** | Recipe ingredients mapped to inventory items | Configuracion |
| 4 | **Estructura** | Inventory items enriched with purchase/stock units, conversion factors, families | Alineamiento |
| 5 | **Normalizacion** | Unit conversions validated, deduction logic verified, data consistency checks | Estructura |

### Dashboard View (Standardization Hub)

**Layout:** The main dashboard shows:

- **Progress overview** — Visual progress bar or card-based progress per section (e.g., "Clasificacion: Complete", "Configuracion: 3/5 steps done", "Alineamiento: Not started")
- **Section cards** — Each section is a clickable card showing:
  - Status (Not started / In progress / Complete)
  - Completion percentage
  - Brief description of what this section does
  - "Continue" or "Start" button
- **Overall standardization score** — A single metric (e.g., 45%) showing how standardized the restaurant is
- **AI assistant** — Persistent sidebar, always available

### Section-by-Section Experience

#### 4.1 Clasificacion

**Goal:** Establish the restaurant's operational identity.

**What the operator provides:**
- Restaurant type (Casual, Cafeteria, Fine Dining, etc.)
- Description of the restaurant's concept and cuisine
- Number of stations/areas in the kitchen
- Service style (table service, counter, delivery, etc.)

**How it works:**
- AI generates a classification based on onboarding data
- Operator reviews and adjusts
- AI generates a narrative description of the restaurant

**Output:** Restaurant classification record — used by all subsequent sections for context-aware suggestions.

#### 4.2 Configuracion

**Goal:** Set up the measurement and categorization system.

**What gets configured:**
- **Inventory units** — Stock units (kg, g, L, ml, pza) and purchase units (box, bag, case) with conversion factors
- **Families** — Ingredient groupings (Lacteos, Carnes, Verduras, Abarrotes, etc.)
- **Categories** — Perecedero vs No perecedero
- **Recipe units** — Cooking measurement units (cucharada, taza, pizca, etc.)

**How it works:**
- System pre-loads defaults based on restaurant type (from Clasificacion)
- Operator reviews and customizes
- AI runs consistency checks: "You have 'box' as a purchase unit but no conversion to kg — should we set that up?"
- Operator can add custom units specific to their operation

**Output:** Complete unit/family/category configuration — the measurement language of the restaurant.

#### 4.3 Alineamiento

**Goal:** Map every recipe ingredient to a standardized inventory item.

**What the operator provides:**
- Recipes (uploaded via file or entered conversationally)
- For each recipe: name, ingredients, quantities, preparation steps

**How it works:**
- Operator uploads recipe files (PDF, Excel, photos) or dictates recipes to the AI
- AI extracts ingredients and suggests matching inventory items
- Operator confirms, adjusts, or creates new inventory items
- AI identifies gaps: "This ingredient (cream cheese) doesn't match any inventory item. Should I create one?"

**What gets aligned:**
- Each recipe ingredient → an inventory item
- Each ingredient quantity → a standardized unit
- Orphan ingredients flagged for resolution

**Output:** Complete recipe-to-inventory mapping. Every recipe ingredient is linked to a standardized inventory item.

#### 4.4 Estructura

**Goal:** Enrich every inventory item with full operational metadata.

**What gets structured per item:**
- Stock unit (how it's counted in inventory — e.g., kg)
- Purchase unit (how it's bought — e.g., box)
- Purchase-to-stock conversion factor (1 box = 10 kg)
- Family assignment (Lacteos, Carnes, etc.)
- Category (Perecedero / No perecedero)

**How it works:**
- AI proposes enrichment for all items based on context (restaurant type, common industry patterns)
- Operator reviews in an editable table view
- Processed in two waves: Perecederos first, then No perecederos
- AI handles exceptions: unknown units, missing families, ambiguous items

**Output:** Fully enriched inventory — every item has units, conversion factors, family, and category.

#### 4.5 Normalizacion

**Goal:** Validate that all data is consistent and ready for operational use.

**What gets validated:**
- All unit conversions resolve correctly (no circular references, no missing factors)
- All recipe ingredients can be deducted from inventory
- Family assignments are consistent
- No orphan items (inventory items not used by any recipe)
- No orphan recipes (recipes with unresolved ingredients)

**How it works:**
- System runs automated validation checks
- AI presents a report: "15 items validated successfully. 3 items need attention."
- Operator resolves flagged issues with AI guidance
- Final validation confirms the restaurant is ready for Manual Operativo generation

**Output:** Validated, consistent operational data. The foundation is complete.

---

## 5. Phase 3 — Manual Operativo

### Purpose

Transform all structured data into a living operational dashboard that the operator uses daily. This is the **payoff** — the moment where all the standardization work becomes visible, actionable intelligence.

### What the Manual Operativo Contains

#### 5.1 KPI Dashboard

**Key metrics displayed:**
- Standardization score (overall %)
- Standardization by dimension (Recipes, Inventory, Units, Families)
- Number of standardized recipes vs. total
- Number of fully structured inventory items vs. total
- Consistency score (from Normalizacion validation)
- Estimated theoretical cost per recipe (when data allows)

#### 5.2 Standardization Dimensions

**Visual breakdown of each dimension:**
- **Recipes** — How many recipes are fully standardized (ingredients, quantities, units all resolved)
- **Inventory** — How many items have complete metadata (units, families, factors)
- **Units** — How many conversion factors are defined and validated
- **Families** — Coverage of inventory items across families
- **Processes** — (Future) SOPs and workflow documentation

Each dimension shows a progress indicator and areas that need attention.

#### 5.3 Improvement Areas & Suggestions

**AI-generated insights:**
- "You have 12 recipes without standardized quantities — start with your top 5 sellers"
- "3 inventory items are missing purchase-to-stock conversion factors"
- "Your 'Verduras' family has 25 items but no sub-grouping — consider splitting into Hojas, Raices, Frutas"
- "Based on your recipe volumes, these 5 items represent 60% of your cost — prioritize their accuracy"

#### 5.4 AI Virtual Assistant (Interpretation Mode)

In this phase, the AI assistant shifts from **guide mode** to **interpretation mode**:
- Helps the operator understand what the numbers mean
- Suggests priorities: "Focus on standardizing your top 10 selling recipes first"
- Explains deviations: "Your theoretical cost for Tacos al Pastor is $45 per portion — is that aligned with your pricing?"
- Answers operational questions: "How does my inventory coverage compare to what you'd recommend?"

### Manual Operativo as Living Document

The Manual Operativo is **not static**. It updates automatically as the operator:
- Adds or modifies recipes
- Updates inventory items
- Changes unit conversions
- Completes more standardization sections

Every change in the Standardization phase immediately reflects in the Manual Operativo.

---

## 6. The Living Cycle

### The Continuous Loop

The experience is not linear — it's a **living cycle**:

```
Onboarding (once)
    ↓
Standardization (iterative)
    ↓ ↑
Manual Operativo (always updating)
```

**After initial setup, the operator returns to:**
- **Standardization sections** — to add new recipes, update inventory, adjust units
- **Manual Operativo** — to check KPIs, review suggestions, interpret data

**Every update flows through:**
1. Operator modifies data in a Standardization section
2. System re-validates (Normalizacion runs automatically)
3. Manual Operativo updates in real-time
4. AI generates new insights based on changes

### Temporal Cadence

| Frequency | What the operator does |
|---|---|
| **Daily** | Checks Manual Operativo dashboard, reviews AI suggestions |
| **Weekly** | Updates inventory counts, reviews KPI trends |
| **Monthly** | Adds new recipes, adjusts seasonal items, reviews cost dimensions |
| **As needed** | Responds to AI alerts, resolves flagged inconsistencies |

---

## 7. AI Assistant — Persistent Companion

### Always Present

The AI assistant is available across all phases as a **persistent sidebar** on the right side of the screen. It adapts its behavior based on context:

| Phase | AI Behavior |
|---|---|
| **Onboarding** | Welcomes, explains Zenet, asks discovery questions about the restaurant |
| **Standardization** | Guides through each section, suggests data, resolves ambiguities, handles file uploads |
| **Manual Operativo** | Interprets data, suggests priorities, answers operational questions |
| **Returning visit** | Remembers context, highlights what changed, suggests next actions |

### Key AI Capabilities

1. **File Understanding** — Can process PDFs, Excel files, and photos of recipes/inventory lists
2. **Contextual Suggestions** — Knows the restaurant type, existing data, and industry patterns
3. **Gap Detection** — Identifies missing data and guides the operator to complete it
4. **Natural Language** — Speaks in the operator's language (Spanish, practical terms)
5. **Memory** — Remembers previous conversations and decisions across sessions

### AI Guardrails

- Never makes changes without operator confirmation
- Always explains WHY it's suggesting something
- Flags uncertainty: "I'm 80% sure this ingredient maps to 'Queso Oaxaca' — can you confirm?"
- Defers to the operator's domain knowledge

---

## 8. User Flows by Persona

### Owner-Operator Flow

```
Sign Up → Restaurant Profile → Dashboard
    → Delegates Standardization to Chef/Manager
    → Checks Manual Operativo weekly
    → Reviews KPIs and cost insights
    → Uses AI to interpret data and plan
```

**Key screens:** Dashboard, Manual Operativo, KPI overview
**Time investment:** 30 min onboarding, 15 min/week ongoing

### Kitchen Manager / Chef Flow

```
Invited by Owner → Accepts invite → Sees Dashboard
    → Works through Standardization sections (primary user)
    → Uploads recipes, validates ingredients, structures inventory
    → Uses AI heavily for data entry assistance
    → Reviews Manual Operativo for completeness
```

**Key screens:** Standardization sections, AI chat, editable tables
**Time investment:** 2-4 hours initial standardization, 30 min/week ongoing

### Admin / Accountant Flow

```
Invited by Owner → Accepts invite → Sees Dashboard
    → Views Manual Operativo (read-focused)
    → Exports data for cost analysis
    → Reviews inventory structure for purchasing decisions
```

**Key screens:** Manual Operativo, exports, inventory overview
**Time investment:** 15 min/week, focused on data consumption

---

## 9. Information Architecture

### Navigation Structure

```
Zenet App
├── Dashboard (Home)
│   ├── Standardization Progress Overview
│   ├── Quick Actions
│   └── AI Assistant Sidebar
│
├── Standardization
│   ├── Clasificacion
│   ├── Configuracion
│   ├── Alineamiento
│   ├── Estructura
│   └── Normalizacion
│
├── Manual Operativo
│   ├── KPI Dashboard
│   ├── Standardization Dimensions
│   ├── Improvement Areas
│   └── AI Insights
│
├── Settings
│   ├── Restaurant Profile
│   ├── Team Members
│   ├── Billing
│   └── Preferences
│
└── AI Assistant (Persistent Sidebar — available on all screens)
```

### Role-Based Access

| Feature | Owner | Manager/Chef | Admin |
|---|---|---|---|
| Onboarding | Full access | Invited | Invited |
| Standardization sections | Full access | Full access | View only |
| Manual Operativo | Full access | Full access | Full access |
| Settings / Team | Full access | Limited | View only |
| Billing | Full access | No access | View only |
| AI Assistant | Full access | Full access | Full access |

---

## 10. Key Screens Summary

| # | Screen | Phase | Description |
|---|---|---|---|
| 1 | Landing / Sign Up | Onboarding | Account creation, minimal friction |
| 2 | Restaurant Profile | Onboarding | Business info, cuisine type, locations |
| 3 | AI Welcome | Onboarding | Assistant introduces itself, asks discovery questions |
| 4 | Dashboard | All phases | Central hub — progress, quick actions, AI sidebar |
| 5 | Clasificacion | Standardization | Restaurant type and description |
| 6 | Configuracion | Standardization | Units, families, categories setup |
| 7 | Alineamiento | Standardization | Recipe upload + ingredient-to-inventory mapping |
| 8 | Estructura | Standardization | Inventory enrichment (units, factors, families) |
| 9 | Normalizacion | Standardization | Validation and consistency checks |
| 10 | Manual Operativo | Manual Operativo | KPI dashboard, dimensions, AI insights |
| 11 | Settings | Global | Profile, team, billing, preferences |

---

## 11. Open Questions

### Product Decisions Pending

1. **Normalizacion as separate section vs. automatic?** — Should it be a visible section the operator interacts with, or an automated process that runs silently after each Standardization update?

2. **Multi-location experience** — In v1.0, does each location have its own standardization, or is it restaurant-wide? (Recommendation: restaurant-wide for v1, per-location in v2)

3. **Onboarding depth** — How much restaurant info do we capture upfront vs. let the AI discover through conversation during Standardization?

4. **Manual Operativo export** — Should the operator be able to export the Manual Operativo as a PDF for offline use or sharing with staff?

5. **Team collaboration** — Can multiple users work on Standardization simultaneously, or is it sequential? What happens with conflicts?

6. **Notification system** — Does the AI proactively notify the operator when action is needed, or only when they open the app?

7. **Mobile experience** — Is v1.0 desktop-only, or responsive/mobile-first? (Restaurant operators are often on mobile)

8. **Free trial scope** — How much can an operator do before hitting a paywall?

---

*This is a living document. Update as design decisions are made and user testing reveals friction points.*

*Created: April 6, 2026*
*Next review: Before production PRD finalization*
