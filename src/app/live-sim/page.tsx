'use client';

import { useState } from 'react';

interface PersonaResult {
  persona_id: string;
  segment: string;
  job_role: string;
  market: string;
  content_job: string;
  selected_scorer: string;
  scorer_id: string;
  fit_score: number;
  reveal_probability: number;
  will_buy: boolean;
  stripe_session_id: string | null;
  stripe_session_url: string | null;
  stripe_error?: string;
}

interface SimResult {
  simulation: string;
  personas_total: number;
  buyers: number;
  bounced: number;
  conversion_rate: number;
  total_revenue_cents: number;
  platform_take_cents: number;
  stripe_sessions_created: number;
  results: PersonaResult[];
}

export default function LiveSimPage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SimResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runSimulation() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/live-sim', { method: 'POST' });
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
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-amber-500/20 bg-amber-500/5 px-4 py-1.5 text-sm text-amber-400">
            <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
            Live Stripe Test Mode
          </div>
          <h1 className="text-3xl font-bold">Nemotron Persona → Stripe Simulation</h1>
          <p className="mt-2 text-white/50">
            Runs 5 NVIDIA Nemotron personas through the decision model and creates real Stripe test
            checkout sessions for personas that &quot;buy&quot;. Check your Stripe Dashboard to see the sessions appear.
          </p>
        </div>

        {/* Run Button */}
        <button
          onClick={runSimulation}
          disabled={loading}
          className="mb-8 rounded-lg bg-brand-600 px-8 py-3 text-sm font-medium text-white transition hover:bg-brand-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Running Simulation...' : 'Run Live Simulation →'}
        </button>

        {error && (
          <div className="mb-8 rounded-lg border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-400">
            {error}
          </div>
        )}

        {result && (
          <>
            {/* Summary Stats */}
            <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Personas" value={result.personas_total.toString()} />
              <Stat label="Buyers" value={result.buyers.toString()} highlight />
              <Stat label="Conversion" value={`${(result.conversion_rate * 100).toFixed(0)}%`} />
              <Stat label="Stripe Sessions" value={result.stripe_sessions_created.toString()} highlight />
            </div>

            <div className="mb-8 grid gap-4 sm:grid-cols-3">
              <Stat label="Total Revenue" value={`$${(result.total_revenue_cents / 100).toFixed(2)}`} />
              <Stat label="Platform Take (est)" value={`$${(result.platform_take_cents / 100).toFixed(2)}`} />
              <Stat label="Bounced" value={result.bounced.toString()} />
            </div>

            {/* Persona Results */}
            <div className="space-y-4">
              {result.results.map((persona) => (
                <PersonaCard key={persona.persona_id} persona={persona} />
              ))}
            </div>
          </>
        )}

        {/* Explanation */}
        {!result && !loading && (
          <div className="glass-card p-8 mt-8">
            <h2 className="text-lg font-semibold mb-4">What happens when you click:</h2>
            <div className="space-y-3 text-sm text-white/60">
              <Step n={1} text="5 Nemotron personas are evaluated through the deterministic decision model" />
              <Step n={2} text="Each persona's scorer fit, price sensitivity, and trust multiplier are computed" />
              <Step n={3} text="Personas with reveal_probability above their hash threshold → paid_reveal = true" />
              <Step n={4} text="For each buyer, a REAL Stripe Checkout Session is created (test mode)" />
              <Step n={5} text="Sessions appear in your Stripe Dashboard → Developers → Events" />
              <Step n={6} text="If webhooks are configured, checkout.session.completed events fire back to /api/stripe/webhook" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="stat-card text-center">
      <div className={`text-2xl font-bold ${highlight ? 'text-emerald-400' : ''}`}>{value}</div>
      <div className="mt-1 text-xs text-white/40">{label}</div>
    </div>
  );
}

function PersonaCard({ persona }: { persona: PersonaResult }) {
  return (
    <div className={`glass-card p-5 ${persona.will_buy ? 'border-emerald-500/20' : 'border-white/[0.06]'}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <span className="font-mono text-sm font-semibold text-brand-400">{persona.persona_id}</span>
            <span className={`badge ${persona.will_buy ? 'badge-success' : 'bg-white/5 text-white/40 ring-1 ring-white/10'}`}>
              {persona.will_buy ? '✓ BOUGHT' : '✗ bounced'}
            </span>
            <span className="text-xs text-white/30">{persona.market}</span>
          </div>
          <div className="text-sm text-white/70 mb-1">
            {persona.job_role} · <span className="text-white/40">{persona.content_job}</span>
          </div>
          <div className="text-xs text-white/40 capitalize">{persona.segment.replace(/_/g, ' ')}</div>
        </div>

        <div className="text-right shrink-0">
          <div className="text-sm font-medium">{persona.selected_scorer}</div>
          <div className="mt-1 flex items-center gap-3 justify-end text-xs text-white/40">
            <span>fit: <span className="text-white/60">{persona.fit_score.toFixed(2)}</span></span>
            <span>prob: <span className={persona.will_buy ? 'text-emerald-400' : 'text-white/60'}>{persona.reveal_probability.toFixed(2)}</span></span>
          </div>
        </div>
      </div>

      {persona.stripe_session_id && (
        <div className="mt-3 rounded-lg bg-emerald-500/5 border border-emerald-500/10 px-4 py-2">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs text-emerald-400 font-medium">Stripe Session Created</span>
              <div className="font-mono text-xs text-white/40 mt-0.5">{persona.stripe_session_id}</div>
            </div>
            {persona.stripe_session_url && (
              <a
                href={persona.stripe_session_url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-md bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400 transition hover:bg-emerald-500/20"
              >
                Open Checkout →
              </a>
            )}
          </div>
        </div>
      )}

      {persona.stripe_error && (
        <div className="mt-3 rounded-lg bg-red-500/5 border border-red-500/10 px-4 py-2 text-xs text-red-400">
          Error: {persona.stripe_error}
        </div>
      )}
    </div>
  );
}

function Step({ n, text }: { n: number; text: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-500/10 text-[10px] font-bold text-brand-400">
        {n}
      </div>
      <span>{text}</span>
    </div>
  );
}
