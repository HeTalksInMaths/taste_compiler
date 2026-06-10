import Link from "next/link";

export default function MethodologyPage() {
  return (
    <div className="px-6 py-16">
      <div className="mx-auto max-w-4xl">
        <div className="mb-12">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm" style={{ border: "1px solid rgba(255,255,255,0.1)", backgroundColor: "rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.7)" }}>
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: "rgb(52,211,153)" }} />
            NVIDIA Nemotron Persona Simulation
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-white">Methodology</h1>
          <p className="mt-3 text-lg" style={{ color: "rgba(255,255,255,0.5)" }}>
            How we stress-test marketplace assumptions using synthetic personas powered by NVIDIA Nemotron
            before spending a dollar on real acquisition.
          </p>
        </div>

        {/* Pipeline Overview */}
        <div className="glass-card mb-8 p-8">
          <h2 className="text-xl font-bold text-white mb-6">The Pipeline</h2>
          <div className="space-y-0">
            {PIPELINE.map((step, i) => (
              <div key={i} className="relative flex gap-4 pb-8 last:pb-0">
                {i < PIPELINE.length - 1 && (
                  <div className="absolute left-[15px] top-[32px] h-[calc(100%-16px)] w-px" style={{ backgroundColor: "rgba(255,255,255,0.1)" }} />
                )}
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold" style={{ backgroundColor: "rgba(92,124,250,0.1)", color: "rgb(145,167,255)", boxShadow: "0 0 0 1px rgba(92,124,250,0.2)" }}>
                  {i + 1}
                </div>
                <div className="pt-0.5">
                  <div className="font-semibold text-white mb-1">{step.title}</div>
                  <div className="text-sm leading-relaxed" style={{ color: "rgba(255,255,255,0.5)" }}>{step.desc}</div>
                  {step.code && (
                    <div className="mt-2 rounded-lg px-4 py-2 font-mono text-xs overflow-x-auto" style={{ backgroundColor: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.6)" }}>
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
          <h2 className="text-xl font-bold text-white mb-4">Why NVIDIA Nemotron Personas?</h2>
          <div className="space-y-3 text-sm" style={{ color: "rgba(255,255,255,0.6)" }}>
            <p>Traditional market research asks real people expensive questions. We use NVIDIA Nemotron (via Colab AI / Gemini 3.5 Flash) to simulate a panel of 200 personas — 100 per market — each with distinct job roles, content needs, price sensitivity, and AI comfort levels.</p>
            <p>This isn&apos;t a forecast. It&apos;s a stress-test: does the pricing make sense? Does the scorer positioning resonate? Which segments bounce and why? Where is creator supply weakest?</p>
            <p>The LLM panel runs in batches of 10, with deterministic fallback for any malformed responses. Every persona answers the same 7 decision questions, producing probabilities that feed directly into the payment economics simulation.</p>
          </div>
        </div>

        {/* Dual Model */}
        <div className="grid gap-6 md:grid-cols-2 mb-8">
          <div className="glass-card p-6">
            <div className="mb-3 flex items-center gap-2">
              <div className="h-3 w-3 rounded-full" style={{ backgroundColor: "#5c7cfa" }} />
              <h3 className="font-semibold text-white">Deterministic Model</h3>
            </div>
            <p className="text-sm mb-4" style={{ color: "rgba(255,255,255,0.5)" }}>Always runs. Reproducible baseline with fixed seed (20260608).</p>
            <div className="space-y-2 text-xs">
              {[['Seed', '20260608'], ['Reproducible', '✓ always'], ['API calls', '0'], ['Used for', 'price sweeps']].map(([k, v]) => (
                <div key={k} className="flex justify-between" style={{ color: "rgba(255,255,255,0.4)" }}>
                  <span>{k}</span><span className="font-mono">{v}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="glass-card p-6">
            <div className="mb-3 flex items-center gap-2">
              <div className="h-3 w-3 rounded-full" style={{ backgroundColor: "#7c3aed" }} />
              <h3 className="font-semibold text-white">LLM Persona Panel</h3>
            </div>
            <p className="text-sm mb-4" style={{ color: "rgba(255,255,255,0.5)" }}>Optional. NVIDIA Nemotron simulates each persona&apos;s reaction. Falls back to deterministic per-persona if a batch fails.</p>
            <div className="space-y-2 text-xs">
              {[['Model', 'Nemotron / Gemini 3.5'], ['Batch size', '10 personas'], ['API calls', '~20 (200 ÷ 10)'], ['Fallback', 'per-persona deterministic']].map(([k, v]) => (
                <div key={k} className="flex justify-between" style={{ color: "rgba(255,255,255,0.4)" }}>
                  <span>{k}</span><span className="font-mono">{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Scorer Fit */}
        <div className="glass-card mb-8 p-8">
          <h2 className="text-xl font-bold text-white mb-2">Scorer Fit Scoring</h2>
          <p className="text-sm mb-4" style={{ color: "rgba(255,255,255,0.5)" }}>Each persona-scorer pair gets a fit score (0–1) based on segment match, content job keyword overlap, and AI comfort level.</p>
          <div className="rounded-lg p-4 font-mono text-xs overflow-x-auto whitespace-pre" style={{ backgroundColor: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.6)" }}>
{`fit = 0.25 (base)
  + segment_match_bonus    (0.30–0.35)
  + content_keyword_bonus  (0.20–0.35)
  + ai_comfort_modifier    (-0.08 to +0.06)

reveal_prob = try_prob × price_sensitivity × trust_mult
price_sensitivity = sigmoid((price - reference) / (ref × 0.35))
trust_mult = f(paid_uses, rating, ai_comfort, segment)`}
          </div>
        </div>

        {/* CTA cross-link */}
        <div className="glass-card p-8 text-center" style={{ borderColor: "rgba(92,124,250,0.2)" }}>
          <h2 className="text-xl font-bold text-white mb-2">Run the pipeline on your own goal</h2>
          <p className="text-sm mb-5 max-w-lg mx-auto" style={{ color: "rgba(255,255,255,0.45)" }}>
            The Taste Compiler pipeline runs the full taste research → scorer evolution → pair testing flow.
            Create a scorer, then market-test it here.
          </p>
          <Link href="/create" className="inline-block rounded-lg px-6 py-3 text-sm font-medium text-white transition" style={{ background: "linear-gradient(to right, #4c6ef5, #7c3aed)" }}>
            Create Your Own Scorer →
          </Link>
        </div>
      </div>
    </div>
  );
}

const PIPELINE = [
  { title: 'Build sampling frame', desc: 'Deterministic quota construction: 9 segments × weighted allocation across Singapore + US. Targeted personas likely to buy, build, or sell.', code: 'PERSONAS_PER_MARKET = 100 | MARKETS = ["Singapore", "United States"]' },
  { title: 'Generate persona panel', desc: 'Each persona gets a job role, content job-to-be-done, location, channel, AI comfort level, budget sensitivity, and posting frequency. All deterministic from segment + index.', code: null },
  { title: 'Run Nemotron LLM panel (optional)', desc: 'NVIDIA Nemotron simulates each persona\'s reaction to scorer cards in batches of 10. Robust JSON extraction handles varied output formats. Falls back per-persona on failure.', code: 'USE_LLM_PERSONA_PANEL = True | LLM_BATCH_SIZE = 10' },
  { title: 'Compute deterministic decisions', desc: 'Every persona answers 7 questions: scorer fit, price sensitivity (sigmoid), trust multiplier, try probability, reveal probability, custom build likelihood, publish scorer likelihood.', code: 'reveal_prob = try_prob × price_mult × trust | SEED = 20260608' },
  { title: 'Payment economics simulation', desc: 'Convert persona decisions into gross revenue, Stripe fees (3.4% + $0.50 SG / 2.9% + $0.30 US), API costs ($0.35/reveal), platform take (30%), and creator payouts (70%).', code: null },
  { title: 'Price sweep', desc: 'Test 6 price points ($1.99 → $19.99) across all personas. Find the price that maximizes platform take per market.', code: 'PRICE_POINTS = [1.99, 2.99, 4.99, 7.99, 9.99, 19.99]' },
  { title: 'Failure diagnostics', desc: 'Auto-flag: conversion too low/high, one scorer dominates, creator supply weak, custom demand weak.', code: null },
  { title: 'Export artifacts', desc: 'Full JSON packet, per-market CSVs, markdown report. All reproducible from seed.', code: null },
];
