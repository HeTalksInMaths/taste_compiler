# UX Product Narrative — Tasks

## Task 1: Navigation + Homepage
- [ ] Audit current `apps/web/app/layout.tsx` for nav structure
- [ ] Simplify navigation to: Create Scorer, Live Pipeline, Market (remove Dashboard, Live Sim, duplicates)
- [ ] Rewrite `apps/web/app/page.tsx` homepage hero with product headline + subtitle + CTAs
- [ ] Remove provider selector / dev mode toggle from homepage
- [ ] Set default quality target to "trustworthy" wherever a default is shown
- [ ] Deploy and verify homepage renders correctly with new copy

## Task 2: /stages → "Live Pipeline Proof"
- [ ] Rename page title to "Live Pipeline Proof" in `apps/web/app/stages/page.tsx`
- [ ] Add summary subtitle: "This is the agent loop behind each scorer artifact..."
- [ ] Rename "Target Variable" → "Quality Target", "Run Full Pipeline" → "Run Taste Compiler Pipeline"
- [ ] Change default target from first option to "trustworthy"
- [ ] Add collapsible toggle state for each stage's detail content
- [ ] Extract summary line per stage (source count, scorer count, etc.) for collapsed view
- [ ] Move dev labels (🔍+🤖, ⚙️, model IDs) into detail section or tooltip
- [ ] Add "What this proves" card at bottom after pipeline completes
- [ ] Add CTAs: "Create a scorer →" and "Market-test this scorer →"
- [ ] Deploy and verify full pipeline run still works with collapsed UI

## Task 3: /create Flow Polish
- [ ] Rename field labels: "Dynamic Variable" → "Quality Target", "Sample text" → "Reference Text", "Best for" → "Use Case", "Target segments" → "Audience"
- [ ] Update page subtitle to product flow description
- [ ] Remove "from Nemotron panel" badge, replace with cleaner "Demand Preview" header
- [ ] Clarify the two user motivations at the top of /create:
  1. Improve my own text
  2. Create a scorer to sell
- [ ] In "Improve my own text" mode:
  - Reference Text is required
  - The result should emphasize score lift and "Reveal full rewrite with Stripe"
- [ ] In "Create a scorer to sell" mode:
  - Audience, Use Case, and price/reveal intent are emphasized
  - Demand Preview comes before building/running the scorer
  - The result CTA should be "Market-test this scorer"
- [ ] Do not present these as the same motivation — use a clear mode toggle or tab at the top of /create
- [ ] Ensure bridge CTAs appear after scorer generation and match the selected mode
- [ ] Verify the demand-pause flow still works correctly after label changes
- [ ] Deploy and verify /create page works end-to-end in both modes

## Task 4: Consistency Pass
- [ ] Grep all user-facing strings for "goal variable", "raw_text", "Live Sim", "Stages 1-4/1-8" and replace with product terminology
- [ ] Update Market Dynamics page subtitle with "Before selling a scorer..." copy
- [ ] Update `lib/chat-system-prompt.ts` to use consistent product terminology
- [ ] Wrap any remaining technical details (model IDs, provider info) in collapsible sections
- [ ] Final review: walk through Homepage → Create → Run → Results → Market → Pipeline and confirm no jargon leaks
- [ ] Deploy and run full acceptance test
