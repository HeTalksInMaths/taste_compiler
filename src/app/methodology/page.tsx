export default function MethodologyPage() {
  return (
    <div className="px-6 py-16">
      <div className="mx-auto max-w-4xl">
        <div className="mb-12">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-sm text-white/70">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            NVIDIA Nemotron Persona Simulation
          </div>
          <h1 className="text-4xl font-bold tracking-tight">Methodology</h1>
          <p className="mt-3 text-lg text-white/50">
            How we stress-test marketplace assumptions using synthetic personas powered by NVIDIA Nemotron
            before spending a dollar on real acquisition.
          </p>
        </div>

        {/* Pipeline Overview */}
        <div className="glass-card mb-8 p-8">
          <h2 className="text-xl font-bold mb-6">The Pipeline</h2>
          <div className="space-y-0">
            {PIPELINE.map((step, i) => (
              <div key={i} className="relative flex gap-4 pb-8 last:pb-0">
                {/* Connector line */}
                {i < PIPELINE.length - 1 && (
                  <div className="absolute left-[15px] top-[32px] h-[calc(100%-16px)] w-px bg-white/10" />
                )}
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-500/10 text-xs font-bold text-brand-400 ring-1 ring-brand-500/20">
                  {i + 1}
                </div>
                <div className="pt-0.5">
                  <div className="font-semibold mb-1">{step.title}</div>
                  <div className="text-sm text-white/50 leading-relaxed">{step.desc}</div>
                  {step.code && (
                    <div className="mt-2 rounded-lg bg-black/40 border border-white/[0.06] px-4 py-2 font-mono text-xs text-white/60 overflow-x-auto">
                      {step.code}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Why Nemotron */}
        <div className="glass-card mb-8 p-8">
          <h2 className="text-xl font-bold mb-4">Why NVIDIA Nemotron Personas?</h2>
          <div className="prose-sm text-white/60 space-y-3">
            <p>
              Traditional market research asks real people expensive questions. We use NVIDIA Nemotron
              (via Colab AI / Gemini 3.5 Flash) to simulate a panel of 200 personas — 100 per market —
              each with distinct job roles, content needs, price sensitivity, and AI comfort levels.
            </p>
            <p>
              This isn&apos;t a forecast. It&apos;s a stress-test: does the pricing make sense? Does the
              scorer positioning resonate? Which segments bounce and why? Where is creator supply weakest?
            </p>
            <p>
              The LLM panel runs in batches of 10, with deterministic fallback for any malformed responses.
              Every persona answers the same 7 decision questions, producing probabilities that feed
              directly into the payment economics simulation.
            </p>
          </div>
        </div>

        {/* Dual Model Architecture */}
        <div className="grid gap-6 md:grid-cols-2 mb-8">
          <div className="glass-card p-6">
            <div className="mb-3 flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-brand-500" />
              <h3 className="font-semibold">Deterministic Model</h3>
            </div>
            <p className="text-sm text-white/50 mb-4">
              Always runs. Reproducible baseline with fixed seed (20260608). Uses segment base intent,
              scorer fit scoring, price sensitivity sigmoid, and trust multipliers.
            </p>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between text-white/40">
                <span>Seed</span><span className="font-mono">20260608</span>
              </div>
              <div className="flex justify-between text-white/40">
                <span>Reproducible</span><span className="text-emerald-400">✓ always</span>
              </div>
              <div className="flex justify-between text-white/40">
                <span>API calls</span><span className="font-mono">0</span>
              </div>
              <div className="flex justify-between text-white/40">
                <span>Used for</span><span>price sweeps, baselines</span>
              </div>
            </div>
          </div>

          <div className="glass-card p-6">
            <div className="mb-3 flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-purple-500" />
              <h3 className="font-semibold">LLM Persona Panel</h3>
            </div>
            <p className="text-sm text-white/50 mb-4">
              Optional. NVIDIA Nemotron simulates each persona&apos;s reaction to the scorer cards,
              pricing, and trust signals. Falls back to deterministic per-persona if a batch fails.
            </p>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between text-white/40">
                <span>Model</span><span className="font-mono">Nemotron / Gemini 3.5 Flash</span>
              </div>
              <div className="flex justify-between text-white/40">
                <span>Batch size</span><span className="font-mono">10 personas</span>
              </div>
              <div className="flex justify-between text-white/40">
                <span>API calls</span><span className="font-mono">~20 (200 ÷ 10)</span>
              </div>
              <div className="flex justify-between text-white/40">
                <span>Fallback</span><span className="text-amber-400">per-persona deterministic</span>
              </div>
            </div>
          </div>
        </div>

        {/* Segment Sampling Frame */}
        <div className="glass-card mb-8 p-8">
          <h2 className="text-xl font-bold mb-2">Sampling Frame</h2>
          <p className="text-sm text-white/50 mb-6">
            Not random population sampling. Deterministic quota construction targeting people likely to
            post online, write for work, buy &quot;make this more ___&quot; tools, or build/sell scorer functions.
          </p>
          <div className="space-y-3">
            {SAMPLING_FRAME.map((seg) => (
              <div key={seg.segment} className="flex items-center gap-4 rounded-lg bg-white/[0.02] p-3">
                <div className="w-8 text-center">
                  <span className="text-sm font-bold text-brand-400">{(seg.weight * 100).toFixed(0)}%</span>
                </div>
                <div className="flex-1">
                  <div className="text-sm font-medium capitalize">{seg.segment.replace(/_/g, ' ')}</div>
                  <div className="text-xs text-white/40">{seg.jobs}</div>
                </div>
                <div className="text-xs text-white/30">{seg.content}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Decision Model */}
        <div className="glass-card mb-8 p-8">
          <h2 className="text-xl font-bold mb-2">Per-Persona Decision Model</h2>
          <p className="text-sm text-white/50 mb-6">
            Each persona implicitly answers 7 questions. The model produces calibrated probabilities,
            not just yes/no — enabling expected-value revenue calculations.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {DECISIONS.map((d, i) => (
              <div key={i} className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-mono text-brand-400">Q{i + 1}</span>
                  <span className="text-sm font-medium">{d.question}</span>
                </div>
                <div className="text-xs text-white/40">{d.factors}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Scorer Fit Function */}
        <div className="glass-card mb-8 p-8">
          <h2 className="text-xl font-bold mb-2">Scorer Fit Scoring</h2>
          <p className="text-sm text-white/50 mb-4">
            Each persona-scorer pair gets a fit score (0–1) based on segment match, content job keyword overlap,
            and AI comfort level. This drives which scorer each persona selects.
          </p>
          <div className="rounded-lg bg-black/40 border border-white/[0.06] p-4 font-mono text-xs text-white/60 overflow-x-auto whitespace-pre">
{`fit = 0.25 (base)
  + segment_match_bonus    (0.30–0.35)
  + content_keyword_bonus  (0.20–0.35)
  + ai_comfort_modifier    (-0.08 to +0.06)

reveal_prob = try_prob × price_sensitivity × trust_mult
price_sensitivity = sigmoid((price - reference) / (ref × 0.35))
trust_mult = f(paid_uses, rating, ai_comfort, segment)`}
          </div>
        </div>

        {/* Payment Economics */}
        <div className="glass-card mb-8 p-8">
          <h2 className="text-xl font-bold mb-2">Payment Economics</h2>
          <p className="text-sm text-white/50 mb-6">
            Revenue splits are modeled with real Stripe fee structures per market.
          </p>
          <div className="grid gap-4 sm:grid-cols-3">
            <EconCard label="Gross per reveal" formula="price × paid_reveal" />
            <EconCard label="Payment fee" formula="gross × rate + fixed" />
            <EconCard label="Net after fees" formula="gross - payment_fee - api_cost" />
            <EconCard label="Platform take" formula="net × 0.30" />
            <EconCard label="Creator take" formula="net × 0.70" />
            <EconCard label="API cost" formula="~$0.35 / reveal" />
          </div>
        </div>

        {/* Calibration */}
        <div className="glass-card mb-8 p-8">
          <h2 className="text-xl font-bold mb-2">Calibration & Failure Flags</h2>
          <p className="text-sm text-white/50 mb-4">
            The simulator flags potential issues automatically:
          </p>
          <div className="space-y-2">
            {FAILURE_FLAGS.map((flag, i) => (
              <div key={i} className="flex items-start gap-2 rounded-lg bg-amber-500/5 border border-amber-500/10 p-3">
                <span className="text-amber-400 text-xs mt-0.5">⚠</span>
                <span className="text-sm text-white/60">{flag}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 text-xs text-white/30">
            If binary conversion &gt; 50%, the simulator flags it as optimistic and recommends
            using expected-value mode for pitch decks rather than binary bools.
          </div>
        </div>

        {/* Tech Stack */}
        <div className="glass-card p-8">
          <h2 className="text-xl font-bold mb-4">Stack</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {STACK.map((item) => (
              <div key={item.name} className="flex items-center gap-3 rounded-lg bg-white/[0.02] p-3">
                <span className="text-sm font-medium">{item.name}</span>
                <span className="text-xs text-white/40 ml-auto">{item.role}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function EconCard({ label, formula }: { label: string; formula: string }) {
  return (
    <div className="rounded-lg bg-white/[0.02] border border-white/[0.06] p-3">
      <div className="text-xs text-white/40 mb-1">{label}</div>
      <div className="font-mono text-xs text-white/70">{formula}</div>
    </div>
  );
}

const PIPELINE = [
  {
    title: 'Build sampling frame',
    desc: 'Deterministic quota construction: 9 segments × weighted allocation across Singapore + US. No random citizen sampling — only targeted personas likely to buy, build, or sell.',
    code: 'PERSONAS_PER_MARKET = 100 | MARKETS = ["Singapore", "United States"]',
  },
  {
    title: 'Generate persona panel',
    desc: 'Each persona gets a job role, content job-to-be-done, location, channel, AI comfort level, budget sensitivity, and posting frequency. All deterministic from segment + index.',
    code: null,
  },
  {
    title: 'Run Nemotron LLM panel (optional)',
    desc: 'NVIDIA Nemotron simulates each persona\'s reaction to the scorer cards in batches of 10. Robust JSON extraction handles {"responses": [...]}, raw [...], or dict-keyed outputs. Falls back per-persona on failure.',
    code: 'USE_LLM_PERSONA_PANEL = True | LLM_BATCH_SIZE = 10',
  },
  {
    title: 'Compute deterministic decisions',
    desc: 'Every persona answers 7 questions: scorer fit, price sensitivity (sigmoid), trust multiplier, try probability, reveal probability, custom build likelihood, publish scorer likelihood.',
    code: 'reveal_prob = try_prob × price_mult × trust | SEED = 20260608',
  },
  {
    title: 'Payment economics simulation',
    desc: 'Convert persona decisions into gross revenue, Stripe fees (3.4% + $0.50 SG / 2.9% + $0.30 US), API costs ($0.35/reveal), platform take (30%), and creator payouts (70%).',
    code: null,
  },
  {
    title: 'Price sweep',
    desc: 'Test 6 price points ($1.99 → $19.99) across all personas. Find the price that maximizes platform take per market. Uses deterministic model only (LLM would explode call counts).',
    code: 'PRICE_POINTS = [1.99, 2.99, 4.99, 7.99, 9.99, 19.99]',
  },
  {
    title: 'Failure diagnostics',
    desc: 'Auto-flag: conversion too low/high, one scorer dominates, creator supply weak, custom demand weak. Calibration check: binary vs expected-value conversion delta.',
    code: null,
  },
  {
    title: 'Export artifacts',
    desc: 'Full JSON packet, per-market CSVs, markdown report. All reproducible from seed.',
    code: null,
  },
];

const SAMPLING_FRAME = [
  { segment: 'sme_owner_operator', weight: 0.16, jobs: 'SME owner, shop owner, clinic manager, e-commerce operator', content: 'sales copy, customer updates' },
  { segment: 'startup_founder_operator', weight: 0.14, jobs: 'startup founder, product operator, solo SaaS builder', content: 'launch post, investor update' },
  { segment: 'marketing_growth_lead', weight: 0.14, jobs: 'growth marketer, content marketer, brand lead', content: 'ads, landing pages, emails' },
  { segment: 'creator_coach_consultant', weight: 0.13, jobs: 'LinkedIn creator, coach, consultant, newsletter writer', content: 'thought leadership, sales page' },
  { segment: 'sales_bd_customer_success', weight: 0.12, jobs: 'sales manager, BD executive, account manager', content: 'outreach, proposals' },
  { segment: 'agency_freelancer', weight: 0.10, jobs: 'copywriter, SEO freelancer, creative agency lead', content: 'client copy, campaigns' },
  { segment: 'researcher_technical_writer', weight: 0.08, jobs: 'researcher, technical writer, data scientist', content: 'abstracts, tech blogs' },
  { segment: 'student_job_seeker', weight: 0.07, jobs: 'student, job seeker, intern, early-career', content: 'resume, cover letter' },
  { segment: 'skeptical_control', weight: 0.06, jobs: 'ops manager, teacher, finance analyst', content: 'internal memos (rare)' },
];

const DECISIONS = [
  { question: 'Strong use case?', factors: 'segment_base_intent × frequency bonus' },
  { question: 'Which scorer fits?', factors: 'segment match + content keyword overlap + AI comfort' },
  { question: 'Teaser creates trust?', factors: 'paid_uses_demo, avg_rating, ai_comfort, segment' },
  { question: 'Willing to pay?', factors: 'sigmoid(price - reference) based on budget_sensitivity' },
  { question: 'Would build custom?', factors: 'SEGMENT_CUSTOM_BUILD × trust × ai_comfort' },
  { question: 'Would publish scorer?', factors: 'SEGMENT_CREATOR_PUBLISH × creator affinity' },
  { question: 'Why bounce?', factors: 'price/trust weak | scorer irrelevant | AI distrust' },
];

const FAILURE_FLAGS = [
  'Conversion too low (<5%): pay-to-reveal story doesn\'t work for this market',
  'Conversion too high (>80%): simulator is too optimistic, not a real forecast',
  'One scorer dominates (>80%): marketplace variety story is weak',
  'Creator publish rate too low (<3%): supply side of marketplace is anemic',
  'Custom build demand too low (<5%): evaluator build revenue stream unlikely',
];

const STACK = [
  { name: 'NVIDIA Nemotron', role: 'LLM persona simulation' },
  { name: 'Gemini 3.5 Flash', role: 'Colab AI fallback model' },
  { name: 'EvalWeaver v5.1', role: 'Scorer discovery pipeline' },
  { name: 'Next.js 14', role: 'Frontend + API routes' },
  { name: 'Stripe Connect', role: 'Payments + creator payouts' },
  { name: 'Vercel', role: 'Deployment + edge functions' },
  { name: 'fast-check', role: 'Property-based testing' },
  { name: 'Tailwind CSS', role: 'UI styling' },
];
