import Link from "next/link";

const SECTIONS = [
  {
    href: "/market-dynamics/marketplace",
    title: "Browse Scorers",
    description: "Preview score lift on existing scorers. Pay to reveal the full improved text.",
    badge: "4 scorers",
    badgeColor: "rgba(92,124,250,0.1)",
    badgeText: "rgb(145,167,255)",
  },
  {
    href: "/market-dynamics/live-sim",
    title: "Market Test",
    description: "Run personas through the decision model and see who would pay for a Stripe reveal.",
    badge: "Live",
    badgeColor: "rgba(245,158,11,0.1)",
    badgeText: "rgb(251,191,36)",
  },
  {
    href: "/market-dynamics/methodology",
    title: "How It Works",
    description: "How we stress-test demand using synthetic personas before spending on real acquisition.",
    badge: "Methodology",
    badgeColor: "rgba(177,151,252,0.1)",
    badgeText: "rgb(177,151,252)",
  },
];

export default function MarketDynamicsIndexPage() {
  return (
    <div className="px-6 py-16">
      <div className="mx-auto max-w-5xl">
        <div className="mb-12">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-sm" style={{ color: "rgba(255,255,255,0.6)" }}>
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: "rgb(92,124,250)" }} />
            Taste Compiler · Market Testing
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-white">Market</h1>
          <p className="mt-3 text-lg" style={{ color: "rgba(255,255,255,0.5)" }}>
            Before selling a scorer, we simulate whether the target audience would pay to reveal it.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {SECTIONS.map((s) => (
            <Link
              key={s.href}
              href={s.href}
              className="glass-card flex flex-col p-6 transition-all hover:border-white/[0.12] hover:bg-white/[0.05]"
              style={{ textDecoration: "none" }}
            >
              <div
                className="mb-3 self-start rounded-full px-3 py-0.5 text-xs font-medium"
                style={{ backgroundColor: s.badgeColor, color: s.badgeText }}
              >
                {s.badge}
              </div>
              <h2 className="mb-2 text-base font-semibold text-white">{s.title}</h2>
              <p className="text-sm leading-relaxed" style={{ color: "rgba(255,255,255,0.45)" }}>
                {s.description}
              </p>
            </Link>
          ))}
        </div>

        {/* Cross-link to Taste Compiler */}
        <div className="mt-12 glass-card p-8 text-center">
          <h2 className="text-xl font-bold text-white mb-2">Build your own scorer</h2>
          <p className="mb-5 text-sm max-w-lg mx-auto" style={{ color: "rgba(255,255,255,0.45)" }}>
            Use the Taste Compiler pipeline to discover, validate, and evolve a quality scorer for any
            subjective goal — then publish it here.
          </p>
          <Link
            href="/create"
            className="inline-block rounded-lg px-6 py-3 text-sm font-medium text-white transition"
            style={{ background: "linear-gradient(to right, #4c6ef5, #7c3aed)" }}
          >
            Create Your Own Scorer →
          </Link>
        </div>
      </div>
    </div>
  );
}
