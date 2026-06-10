import Link from "next/link";

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

const DECISION_QUESTIONS = [
  'Strong use case?', 'Which scorer fits?', 'Teaser creates trust?',
  'Willing to pay reveal price?', 'Would build custom evaluator?',
  'Would publish scorer?', 'Why would they bounce?',
];

export default function SimulationsPage() {
  return (
    <div className="px-6 py-16">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12">
          <h1 className="text-3xl font-bold text-white">Persona Market Simulation v2.1</h1>
          <p className="mt-2" style={{ color: "rgba(255,255,255,0.5)" }}>
            Deterministic persona decision model across Singapore and United States launch markets.
            100 personas per market, deterministic quota sampling.
          </p>
        </div>

        <div className="mb-8 grid gap-6 md:grid-cols-2">
          <MarketEconCard market="Singapore" currency="SGD" data={ECONOMICS.sg} />
          <MarketEconCard market="United States" currency="USD" data={ECONOMICS.us} />
        </div>

        {/* Price Sweep */}
        <div className="glass-card mb-8 p-6">
          <h2 className="mb-2 text-lg font-semibold text-white">Price Sweep: Revenue vs. Conversion</h2>
          <p className="mb-6 text-sm" style={{ color: "rgba(255,255,255,0.4)" }}>
            Deterministic simulation across 6 price points. Best price by platform take highlighted.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b" style={{ borderColor: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.4)" }}>
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
                    <tr key={row.price} className="border-b" style={{ borderColor: "rgba(255,255,255,0.03)", backgroundColor: isBest ? "rgba(92,124,250,0.05)" : undefined }}>
                      <td className="py-3 font-mono font-semibold text-white">
                        ${row.price.toFixed(2)}
                        {isBest && <span className="ml-2 badge-success" style={{ fontSize: "10px" }}>optimal</span>}
                      </td>
                      <td className="py-3 text-center" style={{ color: "rgba(255,255,255,0.6)" }}>{(row.sg_conversion * 100).toFixed(0)}%</td>
                      <td className="py-3 text-center font-mono text-white">${row.sg_revenue.toFixed(0)}</td>
                      <td className="py-3 text-center" style={{ color: "rgba(255,255,255,0.6)" }}>{(row.us_conversion * 100).toFixed(0)}%</td>
                      <td className="py-3 text-center font-mono text-white">${row.us_revenue.toFixed(0)}</td>
                      <td className="py-3 text-right font-mono font-semibold" style={{ color: "rgb(145,167,255)" }}>${combined.toFixed(0)}</td>
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
            <h2 className="mb-6 text-lg font-semibold text-white">Segment Base Intent</h2>
            <div className="space-y-3">
              {SEGMENT_FRAME.map((seg) => (
                <div key={seg.segment} className="flex items-center gap-3">
                  <div className="w-40 text-sm truncate capitalize" style={{ color: "rgba(255,255,255,0.6)" }}>
                    {seg.segment.replace(/_/g, ' ')}
                  </div>
                  <div className="flex-1 h-5 rounded-full overflow-hidden" style={{ backgroundColor: "rgba(255,255,255,0.04)" }}>
                    <div className="h-full rounded-full opacity-70" style={{ width: `${seg.baseIntent * 100}%`, background: "linear-gradient(to right, #4c6ef5, #748ffc)" }} />
                  </div>
                  <span className="w-10 text-right text-sm font-mono" style={{ color: "rgba(255,255,255,0.5)" }}>
                    {(seg.baseIntent * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Scorer Market Share */}
          <div className="glass-card p-6">
            <h2 className="mb-6 text-lg font-semibold text-white">Scorer Selection Distribution</h2>
            <div className="space-y-4">
              {SCORER_FIT.map((s) => (
                <div key={s.scorer} className="rounded-lg p-4" style={{ border: "1px solid rgba(255,255,255,0.06)", backgroundColor: "rgba(255,255,255,0.02)" }}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-semibold text-white">{s.scorer}</span>
                    <span className="text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>fit: {s.avg_fit.toFixed(2)}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-xs mb-1" style={{ color: "rgba(255,255,255,0.4)" }}>Singapore</div>
                      <div className="h-2 rounded-full" style={{ backgroundColor: "rgba(255,255,255,0.06)" }}>
                        <div className="h-full rounded-full opacity-70" style={{ width: `${s.sg_share * 100}%`, backgroundColor: "#5c7cfa" }} />
                      </div>
                      <div className="text-xs mt-1" style={{ color: "rgba(255,255,255,0.4)" }}>{(s.sg_share * 100).toFixed(0)}%</div>
                    </div>
                    <div>
                      <div className="text-xs mb-1" style={{ color: "rgba(255,255,255,0.4)" }}>United States</div>
                      <div className="h-2 rounded-full" style={{ backgroundColor: "rgba(255,255,255,0.06)" }}>
                        <div className="h-full rounded-full opacity-70" style={{ width: `${s.us_share * 100}%`, backgroundColor: "#7c3aed" }} />
                      </div>
                      <div className="text-xs mt-1" style={{ color: "rgba(255,255,255,0.4)" }}>{(s.us_share * 100).toFixed(0)}%</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Decision Model */}
        <div className="glass-card mt-8 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Deterministic Decision Model</h2>
          <p className="text-sm mb-4" style={{ color: "rgba(255,255,255,0.5)" }}>
            Each persona answers 7 implicit questions based on segment, scorer fit, price sensitivity, and trust:
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {DECISION_QUESTIONS.map((q, i) => (
              <div key={i} className="rounded-lg p-3" style={{ backgroundColor: "rgba(255,255,255,0.02)" }}>
                <div className="text-xs font-mono mb-1" style={{ color: "rgb(145,167,255)" }}>Q{i + 1}</div>
                <div className="text-sm" style={{ color: "rgba(255,255,255,0.7)" }}>{q}</div>
              </div>
            ))}
          </div>
        </div>

        {/* CTA to Create */}
        <div className="mt-8 glass-card p-8 text-center" style={{ borderColor: "rgba(124,58,237,0.2)" }}>
          <h2 className="text-xl font-bold text-white mb-2">See demand for your own scorer?</h2>
          <p className="text-sm mb-4 max-w-lg mx-auto" style={{ color: "rgba(255,255,255,0.5)" }}>
            These results are from the existing Nemotron persona panel. Try creating your own scorer —
            pick a quality target, see estimated demand, and let Taste Compiler generate the taste research.
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

function MarketEconCard({ market, currency, data }: { market: string; currency: string; data: typeof ECONOMICS.sg }) {
  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">{market}</h3>
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
      <div className="text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>{label}</div>
      <div className="text-lg font-semibold" style={{ color: highlight ? "rgb(52,211,153)" : "white" }}>{value}</div>
    </div>
  );
}
