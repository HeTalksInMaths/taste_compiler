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
      const res = await fetch('/api/market-dynamics/live-sim', { method: 'POST' });
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
          <div className="mb-4 inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm" style={{ border: "1px solid rgba(245,158,11,0.2)", backgroundColor: "rgba(245,158,11,0.05)", color: "rgb(251,191,36)" }}>
            <span className="h-2 w-2 rounded-full animate-pulse" style={{ backgroundColor: "rgb(251,191,36)" }} />
            Live Stripe Test Mode
          </div>
          <h1 className="text-3xl font-bold text-white">Nemotron Persona → Stripe Simulation</h1>
          <p className="mt-2" style={{ color: "rgba(255,255,255,0.5)" }}>
            Runs 5 NVIDIA Nemotron personas through the decision model and creates real Stripe test
            checkout sessions for personas that &quot;buy&quot;. Check your Stripe Dashboard to see the sessions appear.
          </p>
        </div>

        <button
          onClick={runSimulation}
          disabled={loading}
          className="mb-8 rounded-lg px-8 py-3 text-sm font-medium text-white transition"
          style={{ backgroundColor: "#4c6ef5", opacity: loading ? 0.5 : 1, cursor: loading ? 'not-allowed' : 'pointer' }}
        >
          {loading ? 'Running Market Test...' : 'Run Market Test →'}
        </button>

        {error && (
          <div className="mb-8 rounded-lg p-4 text-sm" style={{ border: "1px solid rgba(248,113,113,0.2)", backgroundColor: "rgba(248,113,113,0.05)", color: "rgb(248,113,113)" }}>
            {error}
          </div>
        )}

        {result && (
          <>
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

            <div className="space-y-4">
              {result.results.map((persona) => (
                <PersonaCard key={persona.persona_id} persona={persona} />
              ))}
            </div>
          </>
        )}

        {!result && !loading && (
          <div className="glass-card p-8 mt-8">
            <h2 className="text-lg font-semibold text-white mb-4">What happens when you click:</h2>
            <div className="space-y-3 text-sm" style={{ color: "rgba(255,255,255,0.6)" }}>
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
      <div className="text-2xl font-bold" style={{ color: highlight ? "rgb(52,211,153)" : "white" }}>{value}</div>
      <div className="mt-1 text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>{label}</div>
    </div>
  );
}

function PersonaCard({ persona }: { persona: PersonaResult }) {
  return (
    <div className="glass-card p-5" style={{ borderColor: persona.will_buy ? "rgba(16,185,129,0.2)" : "rgba(255,255,255,0.06)" }}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <span className="font-mono text-sm font-semibold" style={{ color: "rgb(145,167,255)" }}>{persona.persona_id}</span>
            <span className={persona.will_buy ? 'badge-success' : 'badge'} style={persona.will_buy ? {} : { backgroundColor: "rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.4)", boxShadow: "0 0 0 1px rgba(255,255,255,0.1)" }}>
              {persona.will_buy ? '✓ BOUGHT' : '✗ bounced'}
            </span>
            <span className="text-xs" style={{ color: "rgba(255,255,255,0.3)" }}>{persona.market}</span>
          </div>
          <div className="text-sm mb-1" style={{ color: "rgba(255,255,255,0.7)" }}>
            {persona.job_role} · <span style={{ color: "rgba(255,255,255,0.4)" }}>{persona.content_job}</span>
          </div>
          <div className="text-xs capitalize" style={{ color: "rgba(255,255,255,0.4)" }}>{persona.segment.replace(/_/g, ' ')}</div>
        </div>

        <div className="text-right shrink-0">
          <div className="text-sm font-medium text-white">{persona.selected_scorer}</div>
          <div className="mt-1 flex items-center gap-3 justify-end text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>
            <span>fit: <span style={{ color: "rgba(255,255,255,0.6)" }}>{persona.fit_score.toFixed(2)}</span></span>
            <span>prob: <span style={{ color: persona.will_buy ? "rgb(52,211,153)" : "rgba(255,255,255,0.6)" }}>{persona.reveal_probability.toFixed(2)}</span></span>
          </div>
        </div>
      </div>

      {persona.stripe_session_id && (
        <div className="mt-3 rounded-lg px-4 py-2" style={{ backgroundColor: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.1)" }}>
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-medium" style={{ color: "rgb(52,211,153)" }}>Stripe Session Created</span>
              <div className="font-mono text-xs mt-0.5" style={{ color: "rgba(255,255,255,0.4)" }}>{persona.stripe_session_id}</div>
            </div>
            {persona.stripe_session_url && (
              <a href={persona.stripe_session_url} target="_blank" rel="noopener noreferrer" className="rounded-md px-3 py-1 text-xs font-medium transition" style={{ backgroundColor: "rgba(16,185,129,0.1)", color: "rgb(52,211,153)" }}>
                Open Checkout →
              </a>
            )}
          </div>
        </div>
      )}

      {persona.stripe_error && (
        <div className="mt-3 rounded-lg px-4 py-2 text-xs" style={{ backgroundColor: "rgba(248,113,113,0.05)", border: "1px solid rgba(248,113,113,0.1)", color: "rgb(248,113,113)" }}>
          Error: {persona.stripe_error}
        </div>
      )}
    </div>
  );
}

function Step({ n, text }: { n: number; text: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold" style={{ backgroundColor: "rgba(92,124,250,0.1)", color: "rgb(145,167,255)" }}>
        {n}
      </div>
      <span>{text}</span>
    </div>
  );
}
