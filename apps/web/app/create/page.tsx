'use client';

import { useState } from 'react';
import Link from 'next/link';

type Mode = 'improve' | 'sell';

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

const GOAL_SUGGESTIONS = ['trustworthy', 'persuasive', 'concise', 'human', 'professional', 'empathetic', 'data-driven', 'actionable', 'funny', 'urgent'];
const CONTENT_JOBS = ['sales copy', 'landing page', 'LinkedIn post', 'email campaign', 'pitch deck', 'newsletter', 'technical blog', 'cover letter', 'proposal', 'social media ad'];
const PRICE_OPTIONS = [{ cents: 299, label: '$2.99' }, { cents: 499, label: '$4.99' }, { cents: 699, label: '$6.99' }, { cents: 999, label: '$9.99' }, { cents: 1499, label: '$14.99' }];

type StepStatus = 'idle' | 'running' | 'done' | 'error';
const STEPS = ['demand', 'research', 'taste_map', 'scorers'] as const;
const STEP_LABELS = ['Demand Preview', 'Taste Research', 'Taste Map', 'Scorer Hypotheses'];

export default function CreateScorerPage() {
  const [mode, setMode] = useState<Mode>('improve');
  const [goal, setGoal] = useState('');
  const [rawText, setRawText] = useState('');
  const [selectedSegments, setSelectedSegments] = useState<string[]>(['startup_founder_operator', 'marketing_growth_lead', 'creator_coach_consultant']);
  const [priceCents, setPriceCents] = useState(499);
  const [bestFor, setBestFor] = useState<string[]>([]);
  const [stepStatuses, setStepStatuses] = useState<StepStatus[]>(['idle', 'idle', 'idle', 'idle']);
  const [stepResults, setStepResults] = useState<(unknown | null)[]>([null, null, null, null]);
  const [stepErrors, setStepErrors] = useState<(string | null)[]>([null, null, null, null]);
  const [running, setRunning] = useState(false);
  const [demandDone, setDemandDone] = useState(false);

  function toggleSegment(id: string) { setSelectedSegments(prev => prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]); }
  function toggleContentJob(job: string) { setBestFor(prev => prev.includes(job) ? prev.filter(j => j !== job) : [...prev, job]); }

  async function callStep(stepIdx: number, previousResult: unknown): Promise<unknown | null> {
    setStepStatuses(prev => prev.map((s, i) => i === stepIdx ? 'running' : s));
    try {
      const res = await fetch('/api/market-dynamics/create-scorer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          goal: goal.trim(), raw_text: rawText.trim(),
          target_segments: selectedSegments, price_cents: priceCents, best_for: bestFor,
          step: STEPS[stepIdx], previous_result: previousResult,
        }),
      });
      if (!res.ok) { const err = await res.json(); throw new Error(typeof err.error === 'string' ? err.error : JSON.stringify(err.error) || `HTTP ${res.status}`); }
      const { result } = await res.json();
      setStepStatuses(prev => prev.map((s, i) => i === stepIdx ? 'done' : s));
      setStepResults(prev => prev.map((r, i) => i === stepIdx ? result : r));
      return result;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error';
      setStepStatuses(prev => prev.map((s, i) => i === stepIdx ? 'error' : s));
      setStepErrors(prev => prev.map((r, i) => i === stepIdx ? msg : r));
      return null;
    }
  }

  async function runDemand() {
    if (!goal.trim()) return;
    if (mode === 'improve' && !rawText.trim()) return;
    setRunning(true);
    setDemandDone(false);
    setStepStatuses(['idle', 'idle', 'idle', 'idle']);
    setStepResults([null, null, null, null]);
    setStepErrors([null, null, null, null]);
    const result = await callStep(0, null);
    if (result) setDemandDone(true);
    setRunning(false);
  }

  async function runBedrockSteps() {
    setRunning(true);
    let prev: unknown = stepResults[0];
    for (let i = 1; i < 4; i++) {
      const result = await callStep(i, prev);
      if (!result) break;
      prev = result;
    }
    setRunning(false);
  }

  const inputStyle = { width: '100%', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)', backgroundColor: 'rgba(255,255,255,0.03)', padding: '10px 16px', fontSize: '14px', color: 'white', outline: 'none' };
  const canRun = goal.trim() && (mode === 'sell' || rawText.trim());

  return (
    <div className="px-6 py-12">
      <div className="mx-auto max-w-5xl">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">Create a Scorer</h1>
          <p className="mt-2 text-sm" style={{ color: 'rgba(255,255,255,0.5)' }}>
            {mode === 'improve'
              ? 'Reference text → Quality target → Run Taste Compiler → Score lift → Reveal with Stripe'
              : 'Quality target → Audience → Demand preview → Run Taste Compiler → Market-test scorer'}
          </p>
        </div>

        {/* Mode Toggle */}
        <div className="glass-card p-4 mb-6">
          <div className="text-xs font-medium mb-3" style={{ color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>What do you want to do?</div>
          <div className="flex gap-3">
            <button
              onClick={() => setMode('improve')}
              className="flex-1 rounded-lg p-4 text-left transition"
              style={mode === 'improve' ? { backgroundColor: 'rgba(92,124,250,0.1)', border: '1px solid rgba(92,124,250,0.3)' } : { border: '1px solid rgba(255,255,255,0.06)', backgroundColor: 'rgba(255,255,255,0.02)' }}
            >
              <div className="text-sm font-medium text-white mb-1">Improve my text</div>
              <div className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>Score your text against a quality target, see the lift, and reveal a rewrite via Stripe.</div>
            </button>
            <button
              onClick={() => setMode('sell')}
              className="flex-1 rounded-lg p-4 text-left transition"
              style={mode === 'sell' ? { backgroundColor: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)' } : { border: '1px solid rgba(255,255,255,0.06)', backgroundColor: 'rgba(255,255,255,0.02)' }}
            >
              <div className="text-sm font-medium text-white mb-1">Create a scorer to sell</div>
              <div className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>Build a scorer artifact, estimate demand with personas, and market-test it.</div>
            </button>
          </div>
        </div>

        {/* Input Form */}
        <div className="glass-card p-6 mb-6">
          {/* Quality Target */}
          <div className="mb-5">
            <label className="text-sm font-medium mb-2 block text-white">Quality Target</label>
            <input type="text" value={goal} onChange={e => setGoal(e.target.value)} placeholder='"trustworthy", "persuasive", "human"' style={inputStyle} />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {GOAL_SUGGESTIONS.map(g => (
                <button key={g} onClick={() => setGoal(g)} className="rounded-full px-3 py-1 text-xs transition" style={goal === g ? { backgroundColor: '#4c6ef5', color: 'white' } : { border: '1px solid rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.5)' }}>{g}</button>
              ))}
            </div>
          </div>

          {/* Reference Text — required in improve mode, optional in sell mode */}
          <div className="mb-5">
            <label className="text-sm font-medium mb-2 block text-white">
              Reference Text {mode === 'improve' && <span style={{ color: 'rgb(248,113,113)' }}>*</span>}
            </label>
            <textarea
              value={rawText}
              onChange={e => setRawText(e.target.value)}
              placeholder={mode === 'improve' ? "Paste the text you want to improve..." : "Optional — paste example text for context"}
              rows={3}
              style={{ ...inputStyle, resize: 'none' }}
            />
            {mode === 'improve' && !rawText.trim() && goal.trim() && (
              <div className="text-[11px] mt-1" style={{ color: 'rgb(251,191,36)' }}>Reference text is required to generate a score lift.</div>
            )}
          </div>

          {/* Audience — emphasized in sell mode */}
          {mode === 'sell' && (
            <>
              <div className="mb-5">
                <label className="text-sm font-medium mb-2 block text-white">Audience</label>
                <div className="flex flex-wrap gap-2">
                  {SEGMENTS.map(seg => (
                    <button key={seg.id} onClick={() => toggleSegment(seg.id)} className="rounded-full px-3 py-1.5 text-xs transition" style={selectedSegments.includes(seg.id) ? { backgroundColor: 'rgba(16,185,129,0.2)', color: 'rgb(52,211,153)', boxShadow: '0 0 0 1px rgba(16,185,129,0.3)' } : { border: '1px solid rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.5)' }}>
                      {seg.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mb-5">
                <label className="text-sm font-medium mb-2 block text-white">Use Case</label>
                <div className="flex flex-wrap gap-2">
                  {CONTENT_JOBS.map(job => (
                    <button key={job} onClick={() => toggleContentJob(job)} className="rounded-full px-3 py-1.5 text-xs transition" style={bestFor.includes(job) ? { backgroundColor: 'rgba(92,124,250,0.2)', color: 'rgb(145,167,255)', boxShadow: '0 0 0 1px rgba(92,124,250,0.3)' } : { border: '1px solid rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.5)' }}>
                      {job}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mb-5">
                <label className="text-sm font-medium mb-2 block text-white">Reveal Price</label>
                <div className="flex gap-2">
                  {PRICE_OPTIONS.map(p => (
                    <button key={p.cents} onClick={() => setPriceCents(p.cents)} className="rounded-lg px-4 py-2 text-sm font-mono transition" style={priceCents === p.cents ? { backgroundColor: '#4c6ef5', color: 'white' } : { border: '1px solid rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.5)' }}>
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          <button
            onClick={runDemand}
            disabled={running || !canRun}
            className="w-full rounded-lg py-3 text-sm font-medium text-white transition"
            style={{ background: 'linear-gradient(to right, #4c6ef5, #7c3aed)', opacity: !canRun || running ? 0.4 : 1, cursor: !canRun || running ? 'not-allowed' : 'pointer' }}
          >
            {running && !demandDone ? 'Estimating...' : mode === 'sell' ? 'Estimate Demand →' : 'Run Taste Compiler →'}
          </button>
        </div>

        {/* Pipeline progress */}
        {!stepStatuses.every(s => s === 'idle') && (
          <div className="mb-6 flex items-center justify-center gap-2 flex-wrap">
            {STEP_LABELS.map((label, i) => {
              const status = stepStatuses[i];
              const style = status === 'done' ? { backgroundColor: 'rgba(16,185,129,0.1)', color: 'rgb(52,211,153)', boxShadow: '0 0 0 1px rgba(16,185,129,0.2)' }
                : status === 'running' ? { backgroundColor: 'rgba(245,158,11,0.1)', color: 'rgb(251,191,36)', boxShadow: '0 0 0 1px rgba(245,158,11,0.2)' }
                : status === 'error' ? { backgroundColor: 'rgba(248,113,113,0.1)', color: 'rgb(248,113,113)', boxShadow: '0 0 0 1px rgba(248,113,113,0.2)' }
                : { backgroundColor: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.3)', boxShadow: '0 0 0 1px rgba(255,255,255,0.1)' };
              return (
                <div key={i} className="flex items-center gap-2">
                  <span className="rounded-full px-3 py-1 text-xs font-medium" style={style}>{label}</span>
                  {i < 3 && <span className="text-xs" style={{ color: 'rgba(255,255,255,0.2)' }}>→</span>}
                </div>
              );
            })}
          </div>
        )}

        {/* Demand Preview */}
        {stepResults[0] != null && <DemandPanel data={stepResults[0]} />}
        {stepErrors[0] && <ErrorBox msg={stepErrors[0]} />}

        {/* Proceed gate */}
        {demandDone && stepStatuses[1] === 'idle' && !running && (
          <div className="mb-6 rounded-xl border p-5 flex items-center justify-between" style={{ borderColor: 'rgba(16,185,129,0.2)', backgroundColor: 'rgba(16,185,129,0.04)' }}>
            <div>
              <div className="text-sm font-medium text-white">
                {mode === 'sell' ? 'Demand looks viable?' : 'Ready to generate scorer?'}
              </div>
              <div className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.4)' }}>
                Next: taste research, taste map, and scorer hypotheses.
              </div>
            </div>
            <button onClick={runBedrockSteps} className="text-xs font-medium rounded-lg px-5 py-2.5 transition" style={{ background: 'linear-gradient(to right, #10b981, #4c6ef5)', color: 'white' }}>
              Continue →
            </button>
          </div>
        )}

        {/* Bedrock steps */}
        {stepStatuses[1] === 'running' && <LoadingBox label="Generating taste research..." />}
        {stepResults[1] != null && <ResearchPanel data={stepResults[1]} />}
        {stepErrors[1] && <ErrorBox msg={stepErrors[1]} />}
        {stepStatuses[2] === 'running' && <LoadingBox label="Building taste map..." />}
        {stepResults[2] != null && <TasteMapPanel data={stepResults[2]} />}
        {stepErrors[2] && <ErrorBox msg={stepErrors[2]} />}
        {stepStatuses[3] === 'running' && <LoadingBox label="Generating scorer hypotheses..." />}
        {stepResults[3] != null && <ScorersPanel data={stepResults[3]} />}
        {stepErrors[3] && <ErrorBox msg={stepErrors[3]} />}

        {/* Mode-specific CTAs after completion */}
        {stepResults[3] != null && mode === 'improve' && (
          <div className="mt-6 rounded-xl border p-5 flex items-center justify-between" style={{ borderColor: 'rgba(92,124,250,0.2)', backgroundColor: 'rgba(92,124,250,0.04)' }}>
            <div>
              <div className="text-sm font-medium text-white">Reveal full rewrite with Stripe</div>
              <div className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.4)' }}>The scorer found ways to improve your text. Pay to reveal the full rewritten version.</div>
            </div>
            <Link href="/market-dynamics/live-sim" className="text-xs font-medium rounded-lg px-5 py-2.5 transition" style={{ background: 'linear-gradient(to right, #4c6ef5, #7c3aed)', color: 'white' }}>
              Reveal with Stripe →
            </Link>
          </div>
        )}

        {stepResults[3] != null && mode === 'sell' && (
          <div className="mt-6 rounded-xl border p-5 flex items-center justify-between" style={{ borderColor: 'rgba(16,185,129,0.2)', backgroundColor: 'rgba(16,185,129,0.04)' }}>
            <div>
              <div className="text-sm font-medium text-white">Market-test this scorer</div>
              <div className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.4)' }}>Simulate how Nemotron personas respond and whether they would pay to reveal results.</div>
            </div>
            <Link href="/market-dynamics" className="text-xs font-medium rounded-lg px-5 py-2.5 transition" style={{ background: 'linear-gradient(to right, #10b981, #4c6ef5)', color: 'white' }}>
              Market-test →
            </Link>
          </div>
        )}

        {/* Always show pipeline proof link */}
        {stepResults[3] != null && (
          <div className="mt-3 text-center">
            <Link href="/stages" className="text-xs transition" style={{ color: 'rgba(255,255,255,0.35)' }}>
              View full pipeline proof →
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

function DemandPanel({ data }: { data: unknown }) {
  const d = data as { segment_demand: Array<{ label: string; reveal_probability: number; estimated_buyers_per_100: number }>; avg_conversion_rate: number; estimated_revenue_per_100_personas: number; estimated_platform_take: number };
  return (
    <div className="glass-card p-6 mb-6">
      <h2 className="text-lg font-semibold text-white mb-4">Demand Preview</h2>
      <div className="grid gap-4 sm:grid-cols-3 mb-6">
        <div className="text-center"><div className="text-2xl font-bold" style={{ color: 'rgb(52,211,153)' }}>{(d.avg_conversion_rate * 100).toFixed(0)}%</div><div className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>Avg conversion</div></div>
        <div className="text-center"><div className="text-2xl font-bold text-white">${d.estimated_revenue_per_100_personas.toFixed(0)}</div><div className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>Revenue / 100</div></div>
        <div className="text-center"><div className="text-2xl font-bold" style={{ color: 'rgb(145,167,255)' }}>${d.estimated_platform_take.toFixed(0)}</div><div className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>Platform take</div></div>
      </div>
      <div className="space-y-2">
        {d.segment_demand.map(seg => (
          <div key={seg.label} className="flex items-center gap-3">
            <span className="w-36 text-xs truncate" style={{ color: 'rgba(255,255,255,0.5)' }}>{seg.label}</span>
            <div className="flex-1 h-4 rounded-full overflow-hidden" style={{ backgroundColor: 'rgba(255,255,255,0.04)' }}>
              <div className="h-full rounded-full opacity-70" style={{ width: `${seg.reveal_probability * 100}%`, background: 'linear-gradient(to right, #4c6ef5, #10b981)' }} />
            </div>
            <span className="w-12 text-right text-xs font-mono" style={{ color: 'rgba(255,255,255,0.5)' }}>{seg.estimated_buyers_per_100}/100</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ResearchPanel({ data }: { data: unknown }) {
  const d = data as Record<string, string>;
  return (
    <div className="glass-card p-6 mb-6">
      <h2 className="text-lg font-semibold text-white mb-4">Taste Research</h2>
      <div className="space-y-4 text-sm" style={{ color: 'rgba(255,255,255,0.6)' }}>
        {Object.entries(d).map(([key, val]) => (
          <div key={key}><div className="text-xs font-medium uppercase mb-1" style={{ color: 'rgba(255,255,255,0.4)', letterSpacing: '0.05em' }}>{key.replace(/_/g, ' ')}</div><p className="leading-relaxed">{String(val).slice(0, 400)}</p></div>
        ))}
      </div>
    </div>
  );
}

function TasteMapPanel({ data }: { data: unknown }) {
  const d = data as Record<string, unknown>;
  const colors: Record<string, string> = { rewards: 'rgb(52,211,153)', punishes: 'rgb(248,113,113)', preserves: 'rgb(251,191,36)' };
  return (
    <div className="glass-card p-6 mb-6">
      <h2 className="text-lg font-semibold text-white mb-4">Taste Map</h2>
      <div className="grid gap-4 sm:grid-cols-3">
        {(['rewards', 'punishes', 'preserves'] as const).map(key => {
          const items = d[key];
          if (!Array.isArray(items)) return null;
          return (
            <div key={key}><div className="text-xs font-medium uppercase mb-2" style={{ color: colors[key], letterSpacing: '0.05em' }}>{key}</div><ul className="space-y-1">{items.map((item, i) => <li key={i} className="text-sm" style={{ color: 'rgba(255,255,255,0.6)' }}>• {String(item)}</li>)}</ul></div>
          );
        })}
      </div>
    </div>
  );
}

function ScorersPanel({ data }: { data: unknown }) {
  const scorers = Array.isArray(data) ? data : [];
  return (
    <div className="glass-card p-6 mb-6">
      <h2 className="text-lg font-semibold text-white mb-4">Scorer Hypotheses</h2>
      <div className="space-y-3">
        {scorers.map((s: Record<string, unknown>, i: number) => (
          <div key={i} className="rounded-lg p-4" style={{ border: '1px solid rgba(255,255,255,0.06)', backgroundColor: 'rgba(255,255,255,0.02)' }}>
            <div className="text-sm font-semibold text-white mb-1">{String(s.name || `Scorer ${i + 1}`)}</div>
            {!!s.mechanism && <p className="text-xs mb-2" style={{ color: 'rgba(255,255,255,0.5)' }}>{String(s.mechanism)}</p>}
            {!!s.formula_sketch && <div className="rounded-md px-3 py-2 font-mono text-xs" style={{ backgroundColor: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.5)' }}>{String(s.formula_sketch)}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

function LoadingBox({ label }: { label: string }) {
  return <div className="glass-card p-4 mb-6 text-sm animate-pulse" style={{ color: 'rgb(251,191,36)' }}>⟳ {label}</div>;
}

function ErrorBox({ msg }: { msg: string | null }) {
  if (!msg) return null;
  return <div className="mb-6 rounded-lg p-4 text-sm" style={{ border: '1px solid rgba(248,113,113,0.2)', backgroundColor: 'rgba(248,113,113,0.05)', color: 'rgb(248,113,113)' }}>{msg}</div>;
}
