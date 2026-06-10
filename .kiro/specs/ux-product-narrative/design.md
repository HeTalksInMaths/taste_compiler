# UX Product Narrative — Design

## Architecture

No backend changes. All modifications are frontend-only within `apps/web/`:

```
apps/web/
├── app/
│   ├── page.tsx              ← Task 1: Homepage rewrite
│   ├── layout.tsx            ← Task 1: Navigation simplification
│   ├── create/page.tsx       ← Task 3: Field labels + card layout
│   ├── stages/page.tsx       ← Task 2: Collapsible pipeline proof
│   └── market-dynamics/      ← Task 4: Subtitle + terminology
├── components/
│   ├── Navigation.tsx        ← Task 1: Simplified nav (if extracted)
│   └── StageDetail.tsx       ← Task 2: Expandable detail component (new)
└── lib/
    └── chat-system-prompt.ts ← Task 4: Terminology in chatbot prompt
```

## Task 1 Design — Navigation + Homepage

### Navigation
Current nav structure needs audit. Check `layout.tsx` for existing nav links. Simplify to:
- **Create Scorer** → /create
- **Live Pipeline** → /stages
- **Market** → /market-dynamics
- **Demo Run** → /stages?demo=true (optional: auto-run with "trustworthy")

Ask EvalWeaver widget is separate (floating), unaffected.

### Homepage (`app/page.tsx`)
Replace current hero content with:
- H1: "Turn subjective taste into executable scorers."
- Subtitle paragraph (2 sentences max)
- Primary button (gradient): "Create a Scorer →" → /create
- Secondary button (outline): "View Demo Run →" → /stages
- Small text link: "See the live pipeline proof" → /stages

Remove:
- Provider mode selector
- Dev mode toggle
- Any dashboard-style widgets from hero

Keep:
- Overall dark glass aesthetic
- Ask EvalWeaver floating widget

## Task 2 Design — /stages as "Live Pipeline Proof"

### Collapsible Pattern
Use a simple `<details><summary>` or a React state toggle for each stage:

```tsx
// Default: collapsed, showing only summary line
<div className="stage-card">
  <div className="stage-header" onClick={toggle}>
    <span className="badge">✓ Stage 1</span>
    <span className="summary">8 causal factors found from 5 sources</span>
    <span className="chevron">{open ? '▾' : '▸'}</span>
  </div>
  {open && <div className="stage-detail">...full content...</div>}
</div>
```

### Summary extraction per stage:
| Stage | Default visible summary |
|-------|------------------------|
| 1 | "{N} causal factors from {M} research sources" |
| 2 | "{N} nodes, {M} edges in causal graph" |
| 3 | "{N} measurement methods identified" |
| 4 | "{N} scorer hypotheses generated" |
| 5 | "{N} evaluation pairs across train/validation/test" |
| 6 | "{N} scorers evaluated, {M} on Pareto frontier" |
| 7 | "{N} failure patterns, {M} repair instructions" |
| 8 | "{N} repair scorers generated" |

### Bottom cards
After stage results, render:
1. "What this proves" — static card with explanation
2. Two CTA buttons linking to /create and /market-dynamics

## Task 3 Design — /create Flow Polish

### Field mapping (display only — API field names unchanged)
| UI Label | API field |
|----------|-----------|
| Quality Target | goal |
| Reference Text | raw_text |
| Audience | target_segments |
| Use Case | best_for |
| Price | price_cents |

### Card-based results
Replace current section dividers with distinct cards:
1. **Demand Preview** — keep existing DemandPanel, remove "from Nemotron panel" badge text
2. **Taste Research** — keep ResearchPanel as-is (already concise)
3. **Taste Map** — keep TasteMapPanel (already card-formatted with rewards/punishes/preserves)
4. **Scorer Hypotheses** — keep ScorersPanel, add bridge CTAs below

### Bridge CTAs (after final result)
Already partially exists ("Market-test this scorer"). Add:
- "View full pipeline proof →" → /stages

## Task 4 Design — Consistency Pass

### File-by-file changes needed:
1. `app/page.tsx` — terminology in any remaining copy
2. `app/create/page.tsx` — field labels (done in Task 3)
3. `app/stages/page.tsx` — labels (done in Task 2)
4. `app/market-dynamics/` pages — subtitle copy
5. `lib/chat-system-prompt.ts` — replace internal terms with product terms
6. `components/` — any component that renders "goal variable", "live sim", etc.

### Dev info handling
Pattern: wrap technical details in:
```tsx
<details className="mt-4 text-xs opacity-50">
  <summary>Technical details</summary>
  <div>Model: {model}, Region: {region}, ...</div>
</details>
```

## Dependencies between tasks

- Task 1 and Task 2 are independent (can be done in parallel)
- Task 3 depends on Task 1 landing (for consistent nav)
- Task 4 depends on Tasks 1-3 (final consistency sweep)

## Risk

- The /stages page currently renders 8 stages of content inline. Collapsing it requires tracking open/closed state for each stage. Keep it simple with local `useState` array.
- Don't break the pipeline execution flow — the `runAll()` function must still work, just display results differently.
