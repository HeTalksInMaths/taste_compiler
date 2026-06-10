// Data from persona_market_sim_v2_1 notebook
const SEGMENT_FRAME = [
  { segment: 'sme_owner_operator', weight: 0.16, baseIntent: 0.58 },
  { segment: 'startup_founder_operator', weight: 0.14, baseIntent: 0.72 },
  { segment: 'marketing_growth_lead', weight: 0.14, baseIntent: 0.78 },
  { segment: 'creator_coach_consultant', weight: 0.13, baseIntent: 0.75 },
  { segment: 'sales_bd_customer_success', weight: 0.12, baseIntent: 0.65 },
  { segment: 'agency_freelancer', weight: 0.10, baseIntent: 0.70 },
  { segment: 'researcher_technical_writer', weight: 0.08, baseIntent: 0.52 },
  { segment: 'student_job_seeker', weight: 0.07, baseIntent: 0.42 },
  { segment: 'skeptical_control', weight: 0.06, baseIntent: 0.18 },
];

const PRICE_SWEEP = [
  { price: 1.99, sg_conversion: 0.52, sg_revenue: 74.6, us_conversion: 0.55, us_revenue: 78.9 },
  { price: 2.99, sg_conversion: 0.47, sg_revenue: 101.3, us_conversion: 0.50, us_revenue: 107.6 },
  { price: 4.99, sg_conversion: 0.38, sg_revenue: 136.7, us_conversion: 0.42, us_revenue: 151.0 },
  { price: 7.99, sg_conversion: 0.24, sg_revenue: 138.1, us_conversion: 0.28, us_revenue: 161.2 },
  { price: 9.99, sg_conversion: 0.18, sg_revenue: 129.6, us_conversion: 0.22, us_revenue: 158.4 },
  { price: 19.99, sg_conversion: 0.06, sg_revenue: 86.4, us_conversion: 0.08, us_revenue: 115.1 },
];

const SCORER_FIT = [
  { scorer: 'Persuasive Without Hype', sg_share: 0.42, us_share: 0.38, avg_fit: 0.68 },
  { scorer: 'LinkedIn Creator Hook', sg_share: 0.24, us_share: 0.28, avg_fit: 0.62 },
  { scorer: 'Scientific But Readable', sg_share: 0.18, us_share: 0.16, avg_fit: 0.55 },
  { scorer: 'Investor-Ready', sg_share: 0.16, us_share: 0.18, avg_fit: 0.58 },
];

const ECONOMICS = {
  sg: { personas: 100, conversion: 0.38, grossRevenue: 136.7, platformTake: 28.8, creatorTake: 67.2, paymentFees: 8.9, apiCost: 13.3 },
  us: { personas: 100, conversion: 0.42, grossRevenue: 151.0, platformTake: 33.6, creatorTake: 78.4, paymentFees: 8.2, apiCost: 14.7 },
};

export default function SimulationsPage() {
  return (
    <div className="px-6 py-16">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12">
          <h1 className="text-3xl font-bold">Persona Market Simulation v2.1</h1>
          <p className="mt-2 text-white/50">
            Deterministic persona decision model across Singapore and United States launch markets.
            100 personas per market, deterministic quota sampling.
          </p>
        </div>

        {/* Market Economics Comparison */}
        <div className="mb-8 grid gap-6 md:grid-cols-2">
          <MarketEconCard market="Singapore" currency="SGD" data={ECONOMICS.sg} />
          <MarketEconCard market="United States" currency="USD" data={ECONOMICS.us} />
        </div>

        {/* Price Sweep */}
        <div className="glass-card mb-8 p-6">
          <h2 className="mb-2 text-lg font-semibold">Price Sweep: Revenue vs. Conversion</h2>
          <p className="mb-6 text-sm text-white/40">
            Deterministic simulation across 6 price points. Best price by platform take highlighted.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06] text-white/40">
                  <th className="pb-3 text-left font-medium">Price</th>
                  <th className="pb-3 text-center font-medium">SG Conv.</th>
                  <th className="pb-3 text-center font-medium">SG Rev.</th>
                  <th className="pb-3 text-center font-medium">US Conv.</th>
                  <th className="pb-3 text-center font-medium">US Rev.</th>
                  <th className="pb-3 text-right font-medium">Combined</th>
                </tr>
              </thead>
              <tbody>
                {PRICE_SWEEP.map((row) => {
                  const combined = row.sg_revenue + row.us_revenue;
                  const isBest = row.price === 7.99;
                  return (
                    <tr
                      key={row.price}
                      className={`border-b border-white/[0.03] ${isBest ? 'bg-brand-500/5' : ''}`}
                    >
                      <td className="py-3 font-mono font-semibold">
                        ${row.price.toFixed(2)}
                        {isBest && <span className="ml-2 badge-success text-[10px]">optimal</span>}
                      </td>
                      <td className="py-3 text-center text-white/60">{(row.sg_conversion * 100).toFixed(0)}%</td>
                      <td className="py-3 text-center font-mono">${row.sg_revenue.toFixed(0)}</td>
                      <td className="py-3 text-center text-white/60">{(row.us_conversion * 100).toFixed(0)}%</td>
                      <td className="py-3 text-center font-mono">${row.us_revenue.toFixed(0)}</td>
                      <td className="py-3 text-right font-mono font-semibold text-brand-400">${combined.toFixed(0)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="grid gap-8 lg:grid-cols-2">
          {/* Segment Intent */}
          <div className="glass-card p-6">
            <h2 className="mb-6 text-lg font-semibold">Segment Base Intent</h2>
            <div className="space-y-3">
              {SEGMENT_FRAME.map((seg) => (
                <div key={seg.segment} className="flex items-center gap-3">
                  <div className="w-40 text-sm text-white/60 truncate capitalize">
                    {seg.segment.replace(/_/g, ' ')}
                  </div>
                  <div className="flex-1 h-5 rounded-full bg-white/[0.04] overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-brand-600 to-brand-400 opacity-70"
                      style={{ width: `${seg.baseIntent * 100}%` }}
                    />
                  </div>
                  <span className="w-10 text-right text-sm font-mono text-white/50">
                    {(seg.baseIntent * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Scorer Market Share */}
          <div className="glass-card p-6">
            <h2 className="mb-6 text-lg font-semibold">Scorer Selection Distribution</h2>
            <div className="space-y-4">
              {SCORER_FIT.map((s) => (
                <div key={s.scorer} className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-semibold">{s.scorer}</span>
                    <span className="text-xs text-white/40">fit: {s.avg_fit.toFixed(2)}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-xs text-white/40 mb-1">Singapore</div>
                      <div className="h-2 rounded-full bg-white/[0.06]">
                        <div className="h-full rounded-full bg-brand-500 opacity-70" style={{ width: `${s.sg_share * 100}%` }} />
                      </div>
                      <div className="text-xs text-white/40 mt-1">{(s.sg_share * 100).toFixed(0)}%</div>
                    </div>
                    <div>
                      <div className="text-xs text-white/40 mb-1">United States</div>
                      <div className="h-2 rounded-full bg-white/[0.06]">
                        <div className="h-full rounded-full bg-purple-500 opacity-70" style={{ width: `${s.us_share * 100}%` }} />
                      </div>
                      <div className="text-xs text-white/40 mt-1">{(s.us_share * 100).toFixed(0)}%</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Decision Model */}
        <div className="glass-card mt-8 p-6">
          <h2 className="mb-4 text-lg font-semibold">Deterministic Decision Model</h2>
          <p className="text-sm text-white/50 mb-4">
            Each persona answers 7 implicit questions based on segment, scorer fit, price sensitivity, and trust:
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {DECISION_QUESTIONS.map((q, i) => (
              <div key={i} className="rounded-lg bg-white/[0.02] p-3">
                <div className="text-xs text-brand-400 font-mono mb-1">Q{i + 1}</div>
                <div className="text-sm text-white/70">{q}</div>
              </div>
            ))}
          </div>
        </div>

        {/* CTA to Create */}
        <div className="mt-8 glass-card p-8 text-center border-purple-500/20">
          <h2 className="text-xl font-bold mb-2">See demand for your own scorer?</h2>
          <p className="text-white/50 text-sm mb-4 max-w-lg mx-auto">
            These results are from the existing Nemotron persona panel. Try creating your own scorer —
            pick a goal, see estimated demand, and let Bedrock Claude generate the taste research.
          </p>
          <a
            href="/create"
            className="inline-block rounded-lg bg-gradient-to-r from-brand-600 to-purple-600 px-6 py-3 text-sm font-medium text-white transition hover:from-brand-500 hover:to-purple-500"
          >
            Create Your Own Scorer →
          </a>
        </div>
      </div>
    </div>
  );
}

function MarketEconCard({ market, currency, data }: { market: string; currency: string; data: typeof ECONOMICS.sg }) {
  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">{market}</h3>
        <span className="badge-info">{currency}</span>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Metric label="Conversion" value={`${(data.conversion * 100).toFixed(0)}%`} />
        <Metric label="Gross Revenue" value={`$${data.grossRevenue.toFixed(0)}`} />
        <Metric label="Platform Take" value={`$${data.platformTake.toFixed(0)}`} highlight />
        <Metric label="Creator Take" value={`$${data.creatorTake.toFixed(0)}`} />
        <Metric label="Payment Fees" value={`$${data.paymentFees.toFixed(0)}`} />
        <Metric label="API Cost" value={`$${data.apiCost.toFixed(0)}`} />
      </div>
    </div>
  );
}

function Metric({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <div className="text-xs text-white/40">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? 'text-emerald-400' : ''}`}>{value}</div>
    </div>
  );
}

const DECISION_QUESTIONS = [
  'Strong use case?',
  'Which scorer fits?',
  'Teaser creates trust?',
  'Willing to pay reveal price?',
  'Would build custom evaluator?',
  'Would publish scorer?',
  'Why would they bounce?',
];
