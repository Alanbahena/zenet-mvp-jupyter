# Zenet — Business Context for Production Software

**Version:** v1.0
**Last Updated:** April 6, 2026
**Author:** Alan Bahena
**Purpose:** Business context document to inform the production software PRD, architecture, and design decisions.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
   - [The Structural Problem](#the-structural-problem)
   - [The Core Insight](#the-core-insight)
   - [How the Segment Articulates It](#how-the-segment-articulates-it)
2. [Solution](#2-solution)
   - [What Zenet Is](#what-zenet-is)
   - [What Zenet Is NOT](#what-zenet-is-not)
   - [The Operational Sequence](#the-operational-sequence)
   - [The Analogy](#the-analogy)
   - [Framing: Augmentation, Not Replacement](#framing-augmentation-not-replacement)
3. [Market Segmentation](#3-market-segmentation)
   - [Primary Segment](#primary-segment)
   - [Professional Profiles](#professional-profiles)
   - [Cuisine Focus](#cuisine-focus)
   - [Early Adopter Ideal Profile](#early-adopter-ideal-profile)
4. [User Personas](#4-user-personas)
   - [Persona 1: The Owner-Operator](#persona-1-the-owner-operator)
   - [Persona 2: The Kitchen Manager / Executive Chef](#persona-2-the-kitchen-manager--executive-chef)
   - [Persona 3: The Admin / Accountant](#persona-3-the-admin--accountant)
5. [Value Proposition](#5-value-proposition)
   - [Primary Statement](#primary-statement)
   - [Positioning Statement](#positioning-statement)
   - [The "DeepSeek" Positioning](#the-deepseek-positioning)
   - [Value Components](#value-components)
   - [UX as Core Value](#ux-as-core-value)
   - [Hypothetical ROI](#hypothetical-roi)
6. [Differentiation](#6-differentiation)
   - [5 Key Differentiators](#5-key-differentiators)
   - [Competitive Landscape](#competitive-landscape)
7. [Pricing Hypothesis](#7-pricing-hypothesis)
   - [Range](#range)
   - [Proposed Models](#proposed-models-under-evaluation)
   - [Conditions for Willingness to Pay](#conditions-for-willingness-to-pay)
8. [Validation Status](#8-validation-status)
   - [Hypothesis Validation Table](#hypothesis-validation-table-as-of-april-2026)
   - [Key Validators](#key-validators)
   - [Key Validation Insights](#key-validation-insights)
9. [Product Architecture (MVP → Production)](#9-product-architecture-mvp--production)
   - [What the Gradio MVP Proved](#what-the-gradio-mvp-proved)
   - [Production Software Vision](#production-software-vision)
10. [Go-to-Market (Brief)](#10-go-to-market-brief)
    - [Discovery Channels](#discovery-channels)
    - [Key Strategic Decisions](#key-strategic-decisions-mar-apr-2026)
    - [Growth Sequence](#growth-sequence)
11. [Industry Insights](#11-industry-insights)
12. [Guiding Principles](#12-guiding-principles)
13. [Reminders](#reminders)

---

## 1. Problem Statement

### The Structural Problem

Medium-sized restaurants (1-5 locations) don't have a technology problem — they have a **system problem**. They operate with:

1. **Manual, repetitive processes** — Hours lost reviewing, correcting, chasing information. Dependency on Excel, paper, WhatsApp. Constant rework.
2. **No standardization** — No operational manuals, no structured training, each manager has their own method.
3. **Operational overload** — Administrators spend up to 70% of their time on daily tasks. No space to innovate or grow. Constantly putting out fires.
4. **Errors that cost money** — Unexplained waste and shrinkage, manual errors, eroded margins from hidden costs.
5. **Decisions without clear data** — Everything by intuition. No consolidated information. Reactive decisions, not strategic ones.
6. **Growth by trial and error** — No time or support to build structure calmly. Problems multiply with each new location.

### The Core Insight

> The problem is NOT technological. Existing tools (POS, inventory apps, Excel) don't solve it because they are isolated tools — not systems. Many restaurants already have a POS, use Excel or Google Sheets, some have inventory apps. **But operational chaos persists.**

Isolated tools don't solve the lack of process. The correct solution is more complex than a checklist app — and that's exactly why there's space for a well-designed system that understands the human context behind the operation.

### How the Segment Articulates It

- "Inventory never adds up"
- "I spend too much time reconciling numbers"
- "Everyone does things however they want"
- "We don't have a manual for anything"
- "I can't disconnect for even one day"
- "When a key person is missing, everything falls apart"
- "I have POS but it only tracks sales, it doesn't help with purchasing or real inventory"

**Validated by:** ~15 conversations with restaurant operators, chefs, and consultants (Feb-Apr 2026).

---

## 2. Solution

### What Zenet Is

Zenet is a **modular cognitive operating system** for restaurant back-of-house operations. It:

1. **Centralizes** dispersed operations
2. **Standardizes** processes into clear, replicable workflows
3. **Automates** repetitive tasks with intelligent flows
4. **Interprets** operational data (doesn't just store it)
5. **Accompanies** day-to-day operations with virtual assistance

### What Zenet Is NOT

- Not a POS (point of sale)
- Not an isolated inventory app
- Not a complex enterprise ERP
- Not another tool that adds to the chaos
- Not software you "install and figure out"

### The Operational Sequence

Zenet inverts the order. It doesn't start by measuring — it starts by designing.

**Phase 1 — Process Standardization** (Foundation)
Document procedures with standardized recipes, weights, workflows per station. Create SOPs that survive staff turnover.
*Answers: How is each thing supposed to be done in this restaurant?*

**Phase 2 — Inventory Management**
Once processes are standardized, inventory can be cross-referenced against documented recipes. Inputs vs. outputs vs. what the standard says should have been used.
*Answers: Are we using what we should be using according to the designed process?*

**Phase 3 — Cost Interpretation**
Not cost reports — cost interpretation. The difference between theoretical cost (what it should cost per the standardized recipe) and actual cost. When there's deviation, the system doesn't just say "your cost went up" — it says why and what process to fix.
*Answers: Why are the numbers what they are, and what process needs correction?*

> "Most software tells you your cost was 34%. Zenet tells you WHY it was 34% and what process to fix so it becomes 30%." — Derived from conversation with Anna Palazuelos, consultant who supervised 27 Moshi Moshi restaurants and 16 Giornale locations.

### The Analogy

**Other systems are like:** Giving you a hammer, a screwdriver, a saw (isolated tools)
**Zenet is like:** Giving you the house blueprint + the tools + the architect who guides you day by day

### Framing: Augmentation, Not Replacement

Zenet does not automate the chef or replace the owner — it **augments their tools** to do things with greater agility, better knowledge, and fewer resources. AI as an enhancer, not a substitute. There must always be a human behind the system.

**Validation:** When the framing is "Zenet amplifies your operational intelligence" instead of "Zenet automates your operation," fear disappears and adoption willingness increases. (Validated with Victor Murguia, Apr 1 2026)

---

## 3. Market Segmentation

### Primary Segment

| Attribute | Description |
|---|---|
| **Business size** | 1-5 locations |
| **Type** | Independent Restaurants |
| **Stage** | In growth / expansion |
| **Geography** | Tijuana (initial) → Baja California → Northwest Mexico → LATAM |

**Why this segment:**
- Not too small: Already have operational complexity that justifies systematization
- Not too large: Don't have budget for enterprise ERP or dedicated IT team
- Maximum pain point: Suffer operational chaos but don't have adequate solutions for their scale

### Professional Profiles

| Priority | Role | Function |
|---|---|---|
| **Primary** (Decision Makers) | Restaurant owners (1-5 locations), Operations managers | Buy and approve |
| **Secondary** (Influencers) | Executive chefs with operational responsibility, Purchasing/inventory managers | Use daily, recommend |
| **Tertiary** (Advisors) | Gastronomic consultants, Industry suppliers | Channel to reach restaurants |

**Key decision (Apr 2026):** For chains, Zenet needs to win over the executive chef before the owner. The real operational knowledge lives in the middle levels of the kitchen. The chef adopts, the owner pays — two different narratives and two different users.

### Cuisine Focus

- **Primary:** Casual (Independent restaurants)
- **Secondary:** Gourmet/Fine Dining, Bars/Mixology/Dark Kitchens

**Why casual independent restaurants:** Higher transaction volume, more inventory friction, more repetitive processes (more automatable), lower error margin (hidden costs more critical). Besides, a high percentage of restaurants in Mexico and LATAM are independent.

### Early Adopter Ideal Profile

- 1-5 locations in operation
- Type: Casual independent
- Stage: In expansion (opening or planning new location)
- Location: Tijuana
- Recognized pain: Knows they have a process problem, not just a tools problem
- Tech openness: Uses WhatsApp, Excel, maybe Google Sheets. They have a POS.
- Willingness: Open to trying new solutions
- Budget awareness: Conscious of need to invest in operational order

**Validation status:** ~15 conversations. The 1-5 location casual independent segment shows the most recognized pain and openness to solutions.

---

## 4. User Personas

### Persona 1: The Owner-Operator

**Who:** Owner of 1-5 restaurant locations, usually in growth phase
**Daily reality:** Spends 70% of time on daily tasks. Can't disconnect. Always putting out fires.
**Needs from Zenet:**
- Visibility across all locations without micromanaging
- KPIs and cost insights
- Confidence to delegate
- Structure to scale without multiplying chaos
- Having a digital assistance that converts their data and numbers into clear information that allows them to make decisions and plans.

> "I spend 5 hours a week reconciling inventories across 3 locations because each manager counts differently." — Carlos Mendoza, Gerente, Grupo Sabor Autentico

### Persona 2: The Kitchen Manager / Executive Chef

**Who:** Chef with operational responsibility, manages recipes, inventory, and team daily
**Daily reality:** Builds processes from scratch constantly. Depends on personal knowledge. Staff turnover erases progress.
**Needs from Zenet:**
- Standardized recipes with exact weights
- Inventory that cross-references against standards
- Training material that survives staff turnover
- Less time on administrative tasks, more time on cuisine

### Persona 3: The Admin / Accountant

**Who:** Handles numbers, purchasing, cost reports
**Daily reality:** Chases information across WhatsApp, paper, Excel. Numbers never add up.
**Needs from Zenet:**
- Consolidated data exports
- Cost reports that explain WHY, not just WHAT
- Purchase optimization suggestions
- Audit trail for inventory movements

---

## 5. Value Proposition

### Primary Statement

> **"Transform daily operations into intelligent control. Days of work in just hours."**

### Positioning Statement

**For:** Owners and managers of medium restaurants (1-5 locations) in growth
**Who:** Suffer operational chaos due to lack of standardized processes
**Zenet is:** A modular operating system for back-of-house
**That:** Transforms manual operations into automated and intelligent workflows
**Unlike:** POS, isolated inventory apps, or complex enterprise ERPs
**Zenet:** Interprets your operational data and accompanies you day by day with structure and intelligent assistance

### The "DeepSeek" Positioning

> "You're not a point of sale, you're the DeepSeek of the restaurant industry" — Victor Murguia

Zenet is not a POS and doesn't compete with POS. Zenet is **cognitive infrastructure** — like DeepSeek is for AI, Zenet is for restaurant operations. The correct positioning is as an **operational intelligence system**, not as management software.

### Value Components

| Component | What it delivers | Metric |
|---|---|---|
| **Time recovered** | From 5-10 hrs/week lost reconciling → Automated | Hours saved per location per week |
| **Money saved** | Reduced waste, fewer manual errors, optimized purchasing | % reduction in shrinkage, monthly savings |
| **Operational peace of mind** | Less dependency on key people, systems work without owner present | Qualitative (NPS, satisfaction) |
| **Ordered scaling** | Grow without multiplying chaos, standardized processes for new locations | Time to stabilize new location |

### UX as Core Value

The production software must be **truly practical for the real operator**. This means:

- **Smooth, intuitive experience** — the operator should never feel like they're fighting the software
- **Language of the operator, not the system** — A documented process in technical language that nobody understands is the same problem in digital format
- **Onboarding matters as much as the product** — If the restaurant adopts Zenet but the team doesn't understand why each process exists, the cultural problem persists
- **The leader is the most important user** — Give the leader (owner, manager, executive chef) real-time visibility of how processes are being executed — not to control, but to sustain

### Hypothetical ROI

- Time: 28 hrs/month at $200 MXN/hr = $5,600 MXN
- Shrinkage reduction: 3% on $50,000 MXN = $1,500 MXN
- **Total value: ~$7,100 MXN/month vs cost of $1,500 MXN/month = 4.7x ROI**
- **Status:** Hypothesis, not validated with real usage data

---

## 6. Differentiation

### 5 Key Differentiators

**1. System vs Tool**
Others give you isolated tools (POS, inventory app, Excel). Zenet gives you an integrated system with end-to-end flows, active accompaniment, and processes embedded in the tool.

**2. Interpretation vs Management**
Others say "Here's your inventory list." Zenet says "This is what your inventory means and this is what you should do about it." Proactive, not passive.

**3. Accompaniment vs Software**
Others are software you install and figure out. Zenet is a proactive virtual assistant that tells you what to review each morning. A living operational manual, not a static PDF.

**4. Standardization as Entry Point**
Others start with complex features (forecasting, analytics) that require perfect data from day 1. Zenet starts with standardization and inventory (immediate pain), builds clean data from the process, then evolves toward intelligence.

**5. Modular vs Monolithic**
Not "all or nothing" like ERPs, not a single feature like inventory apps. Start simple (inventory + standardization), grow modularly (forecasting, logistics, analytics). Pay for what you use.

### Competitive Landscape

| Competitor Type | Examples | Relationship to Zenet |
|---|---|---|
| **POS** | Toast, Square, Clover | Complementary, not competing. POS = front-of-house. Zenet = back-of-house. |
| **Inventory Apps** | MarketMan, BlueCart | Zenet is the next layer of intelligence on top of inventory tracking |
| **Enterprise ERP** | SAP, Oracle, Odoo | Different segment entirely. ERPs are complex, expensive ($10K+ USD/mo), require IT teams |
| **Manual Tools** | Excel, Google Sheets, WhatsApp | The real competitor. Free but costly in time. Zenet is the evolution of Excel. |

---

## 7. Pricing Hypothesis

### Range

**$1,000 - $2,000 MXN/month per location** (~$55-110 USD)

**Rationale:**
- Accessible for medium restaurants
- Justifiable if it saves 10+ hours/month
- Less than enterprise ERP ($10,000+ USD/month)
- More than simple apps ($200-500 MXN/month)
- Comparable to 1-2 days of manual work cost

### Proposed Models (Under Evaluation)

| Model | Structure | Pros | Cons |
|---|---|---|---|
| **A: Per Location** | $1,500 MXN/month per location, volume discounts | Simple, scales with business | May be expensive for single location |
| **B: Base + Variables** | $1,000 base + $300/location + $100/user | Lower entry point, flexible | More complex to explain |
| **C: By Module** | Core $1,000 + Forecasting $500 + Analytics $500 | Pay for what you use, clear upsell | Complex for MVP (only Core exists) |

### Conditions for Willingness to Pay

1. Saves 10+ hours monthly per location
2. Visibly reduces operational errors
3. Decreases work overload
4. Doesn't add complexity — reduces it
5. Fast onboarding (<1 week)
6. Accessible support in Spanish
7. Clear ROI (value > cost)

**Validation status:** Price validated by Victor Murguia (Apr 1, 2026) as reasonable for the segment. Needs broader validation with 5-10 more conversations.

---

## 8. Validation Status

### Hypothesis Validation Table (as of April 2026)

| Hypothesis | Status | Confidence | Method |
|---|---|---|---|
| **Problem** | Validating qualitatively | Medium-High | ~15 conversations, workshops |
| **Solution** | Validated | High | Victor Murguia call — Apr 1, 2026 |
| **Value** | Validated | High | Victor Murguia call — Apr 1, 2026 |
| **Price** | Validated | Medium | Victor Murguia call — Apr 1, 2026 |
| **Segment** | Partially validated | Medium | Initial conversations |

### Key Validators

| Person | Role | Contribution |
|---|---|---|
| **Victor Murguia** | Gastronomic consultant (Mexicali), international experience | Validated solution, value, and price. Coined "DeepSeek of the restaurant industry" positioning. |
| **Anna Palazuelos** | Consultant, author of 'Recetas para el exito', supervised 27 Moshi Moshi + 16 Giornale | Validated operational sequence: standardization → inventory → cost interpretation |
| **Algira Garzon** | OD Consultant | Validated cultural problem of standardization as competitive advantage |
| **Carlos Sanchez** | A&B Manager (18 years) | Validated problem depth and segment pain |
| **Aldo Alvarado** | Executive Chef | Validated operational reality |
| **Abril Borunda** | Chef (15 years) | Validated operational reality |
| **Victor Mendoza** | QSR Consultant | Industry perspective |

### Key Validation Insights

**Product implications validated in field (Mar 2026):**

1. **Onboarding matters as much as the product** — Zenet needs to design the adoption experience, not just features
2. **System language matters** — Must speak the operator's language, not technical jargon
3. **The leader is the most important user** — Give them real-time visibility to sustain standardization

**Conclusion:** The cultural problem of standardization is a competitive advantage for Zenet, not an obstacle. It means the correct solution is more complex than a checklist app — and that's why there's space for a well-designed system.

---

## 9. Product Architecture (MVP → Production)

### What the Gradio MVP Proved

The MVP (Python + Gradio, local deployment) validated the **cognitive pipeline concept**:

| Section | What it does |
|---|---|
| **Bienvenida** | Captures restaurant identity via conversational AI |
| **Clasificacion** | Generates restaurant classification and description |
| **Configuracion** | Sets up units, families, categories with consistency checks |
| **Alineamiento** | Maps recipe ingredients to inventory items |
| **Estructura** | Enriches inventory items with units, families, purchase factors |
| **Manual Operativo** | Generates operational manual from structured data |

**Key learning:** The AI-guided, section-by-section pipeline works. Operators don't need to understand data modeling — the AI structures their messy real-world knowledge into clean operational data.

### Production Software Vision

The production software rebuilds this as a **multi-tenant SaaS** with:

- **Frontend:** Next.js 15+ (App Router), TypeScript, shadcn/ui + Radix UI, Tailwind CSS
- **Backend:** FastAPI (Python 3.13), Pydantic validation
- **Database:** Supabase (managed PostgreSQL), Row-Level Security for multi-tenancy
- **AI:** Anthropic Claude API, custom agent framework, Langfuse monitoring
- **Deployment:** Vercel (frontend), Railway (backend)

**Additional sections under consideration:**
- Dashboard / Analytics
- Settings / Profile
- Normalization (under evaluation)

---

## 10. Go-to-Market (Brief)

### Discovery Channels

| Channel | Status | Notes |
|---|---|---|
| **LinkedIn (Alan's profile)** | Active | Building community around the problem, not the product. Zenet not mentioned publicly until Month 4-6. |
| **Gastronomic consultants** | Exploring | Consultants reach restaurants before software does. Potential distribution channel. |
| **In-person events** | Planned | Restaurant community events in Tijuana to be mapped. |
| **Cold outreach to owners** | Paused | Segment doesn't give time to strangers. Channel doesn't work. |

### Key Strategic Decisions (Mar-Apr 2026)

- Pause direct investment in Zenet LinkedIn page (no audience, Alan is the channel)
- Pause cold interviews with restaurant owners (segment doesn't yield time to strangers)
- Don't mention Zenet publicly until Month 4-6 (build community around the problem first)
- Consultants as potential early distribution channel (Victor Murguia as potential early ally)

### Growth Sequence

> Identity → Community → System → Product → Company

---

## 11. Industry Insights

Captures from field conversations that inform product design:

| Insight | Source | Implication for Product |
|---|---|---|
| Cook shortage is extreme — talent scarcity | Victor Murguia | Amplifies dependency on key people. Zenet's standardization reduces this dependency. |
| Restaurant average lifespan: 7 years | Victor Murguia | At 6 months should be on track; at 2 years needs green numbers. Early structure is critical. |
| Consultants are very common in independent restaurants | Victor Murguia | Distribution channel opportunity. |
| Problems go beyond internal ops: construction, equipment, ovens | Victor Murguia | Stay focused on back-of-house ops. Don't expand scope prematurely. |
| Cost control is a CONSEQUENCE of standardization, not an independent module | Anna Palazuelos | Architecture: standardization → inventory → cost interpretation. Not the reverse. |
| Chef needs to be won over before the owner (for chains) | Field observation | Two-narrative product: chef adopts, owner pays. |

---

## 12. Guiding Principles

1. **Problem > Solution** — Validate the problem deeply before designing the solution
2. **Segment language > Technical language** — They say "inventory never adds up." We communicate "we help your inventory add up without spending hours." We build a standardization system with data interpretation.
3. **Community > Product** — Identity → Community → System → Product → Company
4. **Iteration > Perfection** — This document is the best current hypothesis, not the final truth
5. **Augment > Automate** — Always a human behind the system. Amplify intelligence, don't replace it.
6. **Practical UX > Feature count** — A smooth experience for the real operator matters more than feature richness. If they can't use it easily, it doesn't matter how powerful it is.

---

## Reminders

- This is a **living document** — update when significant learning occurs
- We are in **pre-product-market fit**
- Everything here are **hypotheses**, not facts
- Validation comes from **real conversations**, not assumptions
- Don't marry any hypothesis — pivot when evidence demands it

---

*Created: April 6, 2026*
*Next review: Post first 5 production software demos*
