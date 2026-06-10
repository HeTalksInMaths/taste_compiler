import Link from "next/link";

const SCORER_CARDS = [
  {
    scorer_id: 'persuasive_without_hype',
    title: 'Persuasive Without Hype',
    dynamic_variable: 'persuasive',
    creator: 'EvalWeaver Seed',
    positioning: 'Makes copy clearer, more credible, and more action-oriented without sounding fake.',
    best_for: ['sales copy', 'landing page', 'launch post', 'proposal'],
    price_to_reveal: 4.99,
    custom_build_price: 39.0,
    avg_rating_demo: 4.7,
    paid_uses_demo: 128,
  },
  {
    scorer_id: 'linkedin_creator_hook',
    title: 'LinkedIn Creator Hook',
    dynamic_variable: 'viral',
    creator: 'Creator A',
    positioning: 'Improves hook, story tension, and comment-worthy ending.',
    best_for: ['LinkedIn post', 'newsletter', 'thought leadership'],
    price_to_reveal: 6.99,
    custom_build_price: 79.0,
    avg_rating_demo: 4.5,
    paid_uses_demo: 42,
  },
  {
    scorer_id: 'scientific_but_readable',
    title: 'Scientific But Readable',
    dynamic_variable: 'scientific',
    creator: 'EvalWeaver Seed',
    positioning: 'Makes claims more evidence-grounded, careful, and easier to read.',
    best_for: ['research summary', 'technical blog', 'grant text'],
    price_to_reveal: 4.99,
    custom_build_price: 59.0,
    avg_rating_demo: 4.8,
    paid_uses_demo: 73,
  },
  {
    scorer_id: 'investor_ready',
    title: 'Investor-Ready',
    dynamic_variable: 'investor-ready',
    creator: 'Creator B',
    positioning: 'Tightens business claims, traction narrative, and investor logic.',
    best_for: ['pitch', 'investor update', 'demo script'],
    price_to_reveal: 9.99,
    custom_build_price: 99.0,
    avg_rating_demo: 4.4,
    paid_uses_demo: 31,
  },
];

export default function MarketplacePage() {
  return (
    <div className="px-6 py-16">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12">
          <h1 className="text-3xl font-bold text-white">Scorer Marketplace</h1>
          <p className="mt-2" style={{ color: "rgba(255,255,255,0.5)" }}>
            Pay-to-reveal quality scorers. Preview your score lift, then unlock the full report.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          {SCORER_CARDS.map((card) => (
            <ScorerCard key={card.scorer_id} card={card} />
          ))}
        </div>

        {/* Custom Build CTA */}
        <div className="mt-12 glass-card p-8 text-center">
          <h2 className="text-2xl font-bold text-white mb-2">Build Your Own Scorer</h2>
          <p className="mb-6 max-w-lg mx-auto text-sm" style={{ color: "rgba(255,255,255,0.5)" }}>
            EvalWeaver discovers, validates, and evolves quality scorers for any subjective goal.
            Publish yours and earn 70% of every reveal.
          </p>
          <div className="flex items-center justify-center gap-4 mb-6">
            <span className="badge-info">Custom build from $39</span>
            <span className="badge-success">70% revenue share</span>
          </div>
          <Link
            href="/create"
            className="inline-block rounded-lg px-6 py-3 text-sm font-medium text-white transition"
            style={{ background: "linear-gradient(to right, #4c6ef5, #7c3aed)" }}
          >
            Create Your Own Scorer →
          </Link>
        </div>

        {/* Cross-link to Taste Compiler runs */}
        <div className="mt-6 rounded-xl border p-5 flex items-center justify-between" style={{ borderColor: "rgba(92,124,250,0.2)", backgroundColor: "rgba(92,124,250,0.04)" }}>
          <div>
            <div className="text-sm font-medium text-white">Already have a scorer from a Taste Compiler run?</div>
            <div className="text-xs mt-0.5" style={{ color: "rgba(255,255,255,0.4)" }}>View run artifacts and validate them against the persona market.</div>
          </div>
          <Link href="/" className="text-xs font-medium rounded-lg px-4 py-2 transition" style={{ backgroundColor: "rgba(92,124,250,0.1)", color: "rgb(145,167,255)" }}>
            View Runs →
          </Link>
        </div>
      </div>
    </div>
  );
}

function ScorerCard({ card }: { card: (typeof SCORER_CARDS)[number] }) {
  return (
    <div className="glass-card flex flex-col p-6 transition-all hover:border-white/[0.12] hover:bg-white/[0.05]">
      <div className="mb-3 flex items-center justify-between">
        <span className="badge-info">{card.dynamic_variable}</span>
        <span className="text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>by {card.creator}</span>
      </div>

      <h3 className="mb-2 text-xl font-semibold text-white">{card.title}</h3>
      <p className="mb-4 text-sm leading-relaxed" style={{ color: "rgba(255,255,255,0.5)" }}>{card.positioning}</p>

      <div className="mb-4 flex flex-wrap gap-1.5">
        {card.best_for.map((tag) => (
          <span key={tag} className="rounded-md px-2 py-0.5 text-xs" style={{ backgroundColor: "rgba(255,255,255,0.04)", color: "rgba(255,255,255,0.5)" }}>
            {tag}
          </span>
        ))}
      </div>

      <div className="mb-4 flex items-center gap-4">
        <div className="flex items-center gap-1">
          {Array.from({ length: 5 }).map((_, i) => (
            <svg key={i} className={`h-3.5 w-3.5 ${i < Math.round(card.avg_rating_demo) ? 'text-amber-400' : ''}`} fill="currentColor" viewBox="0 0 20 20" style={{ color: i < Math.round(card.avg_rating_demo) ? 'rgb(251,191,36)' : 'rgba(255,255,255,0.1)' }}>
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
          ))}
          <span className="ml-1 text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>{card.avg_rating_demo}</span>
        </div>
        <span className="text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>{card.paid_uses_demo} reveals</span>
      </div>

      <div className="mt-auto flex items-center justify-between border-t pt-4" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
        <div>
          <div className="text-2xl font-bold text-white">${card.price_to_reveal.toFixed(2)}</div>
          <div className="text-xs" style={{ color: "rgba(255,255,255,0.3)" }}>per reveal</div>
        </div>
        <div className="text-right">
          <div className="text-sm font-semibold" style={{ color: "rgba(255,255,255,0.6)" }}>${card.custom_build_price.toFixed(0)}</div>
          <div className="text-xs" style={{ color: "rgba(255,255,255,0.3)" }}>custom build</div>
        </div>
      </div>

      <button className="mt-4 w-full rounded-lg py-2.5 text-sm font-medium text-white transition" style={{ backgroundColor: "#4c6ef5" }}>
        Preview Score Lift →
      </button>
    </div>
  );
}
