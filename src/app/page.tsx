export default function HomePage() {
  return (
    <div className="relative">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-32">
        <div className="absolute inset-0 -z-10">
          <div className="absolute left-1/2 top-0 h-[600px] w-[800px] -translate-x-1/2 rounded-full bg-brand-600/10 blur-[120px]" />
          <div className="absolute right-0 top-32 h-[400px] w-[400px] rounded-full bg-purple-600/8 blur-[100px]" />
        </div>
        <div className="mx-auto max-w-4xl text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-sm text-white/70">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            Persona Market Simulator v2.1
          </div>
          <h1 className="text-5xl font-bold tracking-tight sm:text-7xl">
            <span className="gradient-text">EvalWeaver</span>
            <br />
            Taste Marketplace
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-white/50 leading-relaxed">
            Choose &quot;make this more ____&quot;, paste text, see a score-lift teaser,
            then pay to reveal improved outputs. Creators publish custom scorers and earn 70% revenue share.
          </p>
          <div className="mt-10 flex items-center justify-center gap-4">
            <a
              href="/marketplace"
              className="rounded-lg bg-brand-600 px-6 py-3 text-sm font-medium text-white transition hover:bg-brand-500"
            >
              Browse Scorers
            </a>
            <a
              href="/simulations"
              className="rounded-lg border border-white/10 px-6 py-3 text-sm font-medium text-white/80 transition hover:bg-white/5"
            >
              Market Simulations
            </a>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="border-t border-white/[0.06] px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <h2 className="mb-4 text-center text-3xl font-bold">How Pay-to-Reveal Works</h2>
          <p className="mx-auto mb-16 max-w-2xl text-center text-white/50">
            From teaser to full reveal in one Stripe checkout.
          </p>
          <div className="grid gap-6 md:grid-cols-4">
            {STEPS.map((step, i) => (
              <div key={i} className="stat-card relative">
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-brand-500/10 text-brand-400 font-mono text-sm font-bold">
                  {i + 1}
                </div>
                <h3 className="mb-2 font-semibold">{step.title}</h3>
                <p className="text-sm text-white/50 leading-relaxed">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Segments */}
      <section className="border-t border-white/[0.06] px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <h2 className="mb-4 text-center text-3xl font-bold">Launch Segments</h2>
          <p className="mx-auto mb-12 max-w-2xl text-center text-white/50">
            Targeted panel of personas likely to buy, build, or sell scoring functions.
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {SEGMENTS.map((seg) => (
              <div key={seg.id} className="stat-card">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold">{seg.label}</span>
                  <span className="text-xs text-white/40">{(seg.weight * 100).toFixed(0)}% weight</span>
                </div>
                <p className="text-xs text-white/40 mb-3">{seg.why}</p>
                <div className="flex gap-4 text-xs">
                  <div>
                    <span className="text-emerald-400 font-semibold">{(seg.baseIntent * 100).toFixed(0)}%</span>
                    <span className="text-white/30 ml-1">intent</span>
                  </div>
                  <div>
                    <span className="text-brand-400 font-semibold">{(seg.customBuild * 100).toFixed(0)}%</span>
                    <span className="text-white/30 ml-1">build</span>
                  </div>
                  <div>
                    <span className="text-purple-400 font-semibold">{(seg.creatorPublish * 100).toFixed(0)}%</span>
                    <span className="text-white/30 ml-1">publish</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Markets */}
      <section className="border-t border-white/[0.06] px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-8 md:grid-cols-2">
            {MARKETS.map((m) => (
              <div key={m.name} className="glass-card p-6">
                <h3 className="text-xl font-bold mb-1">{m.name}</h3>
                <p className="text-sm text-white/40 mb-4">{m.currency} · {m.locations.join(', ')}</p>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-white/60">Payment rate</span>
                    <span className="font-mono">{(m.paymentRate * 100).toFixed(1)}% + {m.currency} {m.fixedFee.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-white/60">Channels</span>
                    <span className="text-white/50 text-xs">{m.channels.join(', ')}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-white/60">Local hooks</span>
                    <span className="text-white/50 text-xs">{m.hooks.slice(0, 3).join(', ')}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.06] px-6 py-12">
        <div className="mx-auto max-w-6xl text-center text-sm text-white/30">
          EvalWeaver v5.1 · Persona Market Simulator v2.1 · 70/30 creator/platform split
        </div>
      </footer>
    </div>
  );
}

const STEPS = [
  { title: 'Choose Goal', desc: 'Select "make this more persuasive", "more concise", or pick a custom scorer.' },
  { title: 'See Teaser', desc: 'Get a score-lift preview with strengths, weaknesses, and locked insights.' },
  { title: 'Pay to Reveal', desc: 'One-click Stripe checkout. Platform fee 30%, creator earns 70%.' },
  { title: 'Get Full Report', desc: 'Unlock improved text, ranked alternatives, and scoring explanation.' },
];

const SEGMENTS = [
  { id: 'sme_owner_operator', label: 'SME Owner/Operator', weight: 0.16, why: 'Sales posts, customer replies, hiring posts, product pages.', baseIntent: 0.58, customBuild: 0.22, creatorPublish: 0.08 },
  { id: 'startup_founder_operator', label: 'Startup Founder', weight: 0.14, why: 'Pitch copy, launch posts, investor updates, positioning.', baseIntent: 0.72, customBuild: 0.42, creatorPublish: 0.18 },
  { id: 'marketing_growth_lead', label: 'Marketing / Growth', weight: 0.14, why: 'Direct buyer for content improvement and A/B testing.', baseIntent: 0.78, customBuild: 0.45, creatorPublish: 0.22 },
  { id: 'creator_coach_consultant', label: 'Creator / Consultant', weight: 0.13, why: 'Use and monetize personal taste scorer with followers.', baseIntent: 0.75, customBuild: 0.50, creatorPublish: 0.62 },
  { id: 'sales_bd_customer_success', label: 'Sales / BD / CS', weight: 0.12, why: 'Outreach, follow-ups, proposal text, customer comms.', baseIntent: 0.65, customBuild: 0.26, creatorPublish: 0.10 },
  { id: 'agency_freelancer', label: 'Agency / Freelancer', weight: 0.10, why: 'Buy evaluators for client workflows or publish scorers.', baseIntent: 0.70, customBuild: 0.55, creatorPublish: 0.52 },
  { id: 'researcher_technical_writer', label: 'Researcher / Technical Writer', weight: 0.08, why: 'Scientific/readable/credible writing, not just persuasive.', baseIntent: 0.52, customBuild: 0.28, creatorPublish: 0.18 },
  { id: 'student_job_seeker', label: 'Student / Job Seeker', weight: 0.07, why: 'Cover letters, profiles, applications. Lower WTP.', baseIntent: 0.42, customBuild: 0.08, creatorPublish: 0.12 },
  { id: 'skeptical_control', label: 'Skeptical Control', weight: 0.06, why: 'Writes rarely or distrusts AI/pay-to-reveal.', baseIntent: 0.18, customBuild: 0.04, creatorPublish: 0.02 },
];

const MARKETS = [
  {
    name: 'Singapore',
    currency: 'SGD',
    locations: ['CBD', 'Tanjong Pagar', 'Jurong East', 'Paya Lebar', 'One-North'],
    channels: ['LinkedIn', 'WhatsApp Business', 'Instagram', 'email', 'website'],
    hooks: ['SME productivity', 'grant applications', 'regional expansion', 'lean teams'],
    paymentRate: 0.034,
    fixedFee: 0.50,
  },
  {
    name: 'United States',
    currency: 'USD',
    locations: ['San Francisco', 'New York', 'Austin', 'Seattle', 'Miami'],
    channels: ['LinkedIn', 'X/Twitter', 'email', 'website', 'newsletter'],
    hooks: ['startup launch', 'creator monetization', 'sales conversion', 'SaaS growth'],
    paymentRate: 0.029,
    fixedFee: 0.30,
  },
];
