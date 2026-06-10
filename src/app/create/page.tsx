'use client';

import { useState } from 'react';

const SEGMENTS = [
  { id: 'sme_owner_operator', label: 'SME Owner/Operator' },
  { id: 'startup_founder_operator', label: 'Startup Founder' },
  { id: 'marketing_growth_lead', label: 'Marketing / Growth' },
  { id: 'creator_coach_consultant', label: 'Creator / Consultant' },
  { id: 'sales_bd_customer_success', label: 'Sales / BD / CS' },
  { id: 'agency_freelancer', label: 'Agency / Freelancer' },
  { id: 'researcher_technical_writer', label: 'Researcher / Tech Writer' },
  { id: 'student_job_seeker', label: 'Student / Job Seeker' },
];

const GOAL_SUGGESTIONS = [
  'persuasive', 'concise', 'urgent', 'trustworthy', 'funny',
  'professional', 'empathetic', 'data-driven', 'storytelling', 'actionable',
];

const CONTENT_JOBS = [
  'sales copy', 'landing page', 'LinkedIn post', 'email campaign',
  'pitch deck', 'newsletter', 'technical blog', 'cover letter',
  'proposal', 'social media ad', 'product description', 'investor update',
];

const PRICE_OPTIONS = [
  { cents: 299, label: '$2.99' },
  { cents: 499, label: '$4.99' },
  { cents: 699, label: '$6.99' },
  { cents: 999, label: '$9.99' },
  { cents: 1499, label: '$14.99' },
];

interface DemandSegment {
  segment: string;
  label: string;
  base_intent: number;
  reveal_probability: number;
  estimated_buyers_per_100: number;
}

interface ScorerResult {
  goal: string;
  demand_estimate: {
    segment_demand: DemandSegment[];
    avg_conversion_rate: number;
    estimated_revenue_per_100_personas: number;
    estimated_platform_take: number;
  };
  research: Record<string, string> | null;
  taste_map: Record<string, unknown> | null;
  scorer_hypotheses: Array<Record<string, unknown>> | null;
  bedrock_error: string | null;
  model_used: string;
  pipeline_steps_completed: number;
}

export default function CreateScorerPage() {
  const [goal, setGoal] = useState('');
  const [rawText, setRawText] = useState('');
  const [selectedSegments, setSelectedSegments] = useState<string[]>(['startup_founder_operator', 'marketing_growth_lead', 'creator_coach_consultant']);
  const [priceCents, setPriceCents] = useState(499);
  const [bestFor, setBestFor] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScorerResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  function toggleSegment(id: string) {
    setSelectedSegments(prev => prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]);
  }
  function toggleContentJob(job: string) {
    setBestFor(prev => prev.includes(job) ? prev.filter(j => j !== job) : [...prev, job]);
  }

  async function runPipeline() {
    if (!goal.trim() || !rawText.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch('/api/create-scorer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          goal: goal.trim(),
          raw_text: rawText.trim(),
          target_segments: selectedSegments,
          price_cents: priceCents,
          best_for: bestFor,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      setResult(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="px-6 py-16">
      <div className="mx-auto max-w-5xl">
        <div className="mb-8">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-purple-500/20 bg-purple-500/5 px-4 py-1.5 text-sm text-purple-400">
            <span className="h-2 w-2 rounded-full bg-purple-400" />
            Bedrock Claude → EvalWeaver Pipeline
          </div>
          <h1 className="text-3xl font-bold">Create a New Scorer</h1>
          <p className="mt-2 text-white/50">
            Pick a goal, see estimated demand from the Nemotron persona panel, then let Bedrock Claude
            generate taste research + scorer hypotheses. Market-validated product research in one click.
          </p>
        </div>

        {/* Input Form */}
        <div className="glass-card p-6 mb-8">
          {/* Goal */}
          <div className="mb-6">
            <label className="text-sm font-medium mb-2 block">Dynamic Variable (goal)</label>
            <input
              type="text"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder='e.g. "urgent", "trustworthy", "funny"'
              className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:border-brand-500 focus:outline-none"
            />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {GOAL_SUGGESTIONS.map(g => (
                <button
                  key={g}
                  onClick={() => setGoal(g)}
                  className={`rounded-full px-3 py-1 text-xs transition ${goal === g ? 'bg-brand-600 text-white' : 'border border-white/10 text-white/50 hover:bg-white/5'}`}
                >
                  {g}
                </button>
              ))}
            </div>
          </div>

          {/* Raw Text */}
          <div className="mb-6">
            <label className="text-sm font-medium mb-2 block">Sample text to improve</label>
            <textarea
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              placeholder="Paste a piece of text that you want the scorer to improve..."
              rows={3}
              className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:border-brand-500 focus:outline-none resize-none"
            />
          </div>

          {/* Target Segments */}
          <div className="mb-6">
            <label className="text-sm font-medium mb-2 block">Target buyer segments</label>
            <div className="flex flex-wrap gap-2">
              {SEGMENTS.map(seg => (
                <button
                  key={seg.id}
                  onClick={() => toggleSegment(seg.id)}
                  className={`rounded-full px-3 py-1.5 text-xs transition ${selectedSegments.includes(seg.id) ? 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/30' : 'border border-white/10 text-white/50 hover:bg-white/5'}`}
                >
                  {seg.label}
                </button>
              ))}
            </div>
          </div>

          {/* Best For */}
          <div className="mb-6">
            <label className="text-sm font-medium mb-2 block">Best for (content jobs)</label>
            <div className="flex flex-wrap gap-2">
              {CONTENT_JOBS.map(job => (
                <button
                  key={job}
                  onClick={() => toggleContentJob(job)}
                  className={`rounded-full px-3 py-1.5 text-xs transition ${bestFor.includes(job) ? 'bg-brand-500/20 text-brand-300 ring-1 ring-brand-500/30' : 'border border-white/10 text-white/50 hover:bg-white/5'}`}
                >
                  {job}
                </button>
              ))}
            </div>
          </div>

          {/* Price */}
          <div className="mb-6">
            <label className="text-sm font-medium mb-2 block">Reveal price</label>
            <div className="flex gap-2">
              {PRICE_OPTIONS.map(p => (
                <button
                  key={p.cents}
                  onClick={() => setPriceCents(p.cents)}
                  className={`rounded-lg px-4 py-2 text-sm font-mono transition ${priceCents === p.cents ? 'bg-brand-600 text-white' : 'border border-white/10 text-white/50 hover:bg-white/5'}`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Run Button */}
          <button
            onClick={runPipeline}
            disabled={loading || !goal.trim() || !rawText.trim()}
            className="w-full rounded-lg bg-gradient-to-r from-brand-600 to-purple-600 py-3 text-sm font-medium text-white transition hover:from-brand-500 hover:to-purple-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? 'Running EvalWeaver Pipeline via Bedrock...' : 'Estimate Demand + Generate Scorer →'}
          </button>
        </div>

        {error && (
          <div className="mb-8 rounded-lg border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-6">
            {/* Demand Estimate */}
            <div className="glass-card p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">Demand Estimate</h2>
                <span className="badge-info">from Nemotron panel</span>
              </div>
              <div className="grid gap-4 sm:grid-cols-3 mb-6">
                <div className="text-center">
                  <div className="text-2xl font-bold text-emerald-400">{(result.demand_estimate.avg_conversion_rate * 100).toFixed(0)}%</div>
                  <div className="text-xs text-white/40">Avg conversion</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold">${result.demand_estimate.estimated_revenue_per_100_personas.toFixed(0)}</div>
                  <div className="text-xs text-white/40">Revenue / 100 personas</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-brand-400">${result.demand_estimate.estimated_platform_take.toFixed(0)}</div>
                  <div className="text-xs text-white/40">Platform take</div>
                </div>
              </div>
              <div className="space-y-2">
                {result.demand_estimate.segment_demand.map(seg => (
                  <div key={seg.segment} className="flex items-center gap-3">
                    <span className="w-36 text-xs text-white/50 truncate">{seg.label}</span>
                    <div className="flex-1 h-4 rounded-full bg-white/[0.04] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-brand-600 to-emerald-500 opacity-70"
                        style={{ width: `${seg.reveal_probability * 100}%` }}
                      />
                    </div>
                    <span className="w-16 text-right text-xs font-mono text-white/50">
                      {seg.estimated_buyers_per_100}/100
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Research */}
            {result.research && (
              <div className="glass-card p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold">Taste Research</h2>
                  <span className="badge-info">{result.model_used}</span>
                </div>
                <div className="space-y-4 text-sm text-white/60">
                  {Object.entries(result.research).map(([key, val]) => (
                    <div key={key}>
                      <div className="text-xs font-medium text-white/40 uppercase mb-1">{key.replace(/_/g, ' ')}</div>
                      <p className="leading-relaxed">{String(val).slice(0, 500)}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Taste Map */}
            {result.taste_map && (
              <div className="glass-card p-6">
                <h2 className="text-lg font-semibold mb-4">Taste Map</h2>
                <div className="grid gap-4 sm:grid-cols-3">
                  {['rewards', 'punishes', 'preserves'].map(key => {
                    const items = (result.taste_map as Record<string, unknown>)[key];
                    if (!Array.isArray(items)) return null;
                    const colors: Record<string, string> = { rewards: 'text-emerald-400', punishes: 'text-red-400', preserves: 'text-amber-400' };
                    return (
                      <div key={key}>
                        <div className={`text-xs font-medium uppercase mb-2 ${colors[key]}`}>{key}</div>
                        <ul className="space-y-1">
                          {items.map((item: unknown, i: number) => (
                            <li key={i} className="text-sm text-white/60">• {String(item)}</li>
                          ))}
                        </ul>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Scorer Hypotheses */}
            {result.scorer_hypotheses && result.scorer_hypotheses.length > 0 && (
              <div className="glass-card p-6">
                <h2 className="text-lg font-semibold mb-4">Generated Scorer Hypotheses</h2>
                <div className="space-y-4">
                  {result.scorer_hypotheses.map((scorer, i) => (
                    <div key={i} className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-semibold">{String(scorer.name || `Scorer ${i + 1}`)}</span>
                        <span className="text-xs text-white/30">hypothesis</span>
                      </div>
                      {scorer.mechanism ? (
                        <p className="text-sm text-white/50 mb-2">{String(scorer.mechanism)}</p>
                      ) : null}
                      {scorer.formula_sketch ? (
                        <div className="rounded-md bg-black/40 border border-white/[0.06] px-3 py-2 font-mono text-xs text-white/50">
                          {String(scorer.formula_sketch)}
                        </div>
                      ) : null}
                      {Array.isArray(scorer.expected_segments) && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {(scorer.expected_segments as string[]).map((seg: string) => (
                            <span key={seg} className="rounded-full bg-brand-500/10 px-2 py-0.5 text-[10px] text-brand-300">{seg}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Bedrock Error */}
            {result.bedrock_error && (
              <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4">
                <div className="text-sm font-medium text-amber-400 mb-1">Bedrock unavailable — demand estimate still valid</div>
                <div className="text-xs text-white/50">{result.bedrock_error}</div>
                <div className="text-xs text-white/30 mt-2">
                  Steps completed: {result.pipeline_steps_completed}/4 (demand estimate always works, Bedrock steps are optional)
                </div>
              </div>
            )}

            {/* Pipeline Status */}
            <div className="flex items-center justify-center gap-1 py-4">
              {['Demand', 'Research', 'Taste Map', 'Scorers'].map((step, i) => (
                <div key={step} className="flex items-center gap-1">
                  <div className={`rounded-full px-3 py-1 text-xs ${i < result.pipeline_steps_completed ? 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20' : 'bg-white/5 text-white/30 ring-1 ring-white/10'}`}>
                    {step}
                  </div>
                  {i < 3 && <span className="text-white/20 text-xs">→</span>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
