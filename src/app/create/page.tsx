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

const GOAL_SUGGESTIONS = ['persuasive', 'concise', 'urgent', 'trustworthy', 'funny', 'professional', 'empathetic', 'data-driven', 'storytelling', 'actionable'];
const CONTENT_JOBS = ['sales copy', 'landing page', 'LinkedIn post', 'email campaign', 'pitch deck', 'newsletter', 'technical blog', 'cover letter', 'proposal', 'social media ad'];
const PRICE_OPTIONS = [{ cents: 299, label: '$2.99' }, { cents: 499, label: '$4.99' }, { cents: 699, label: '$6.99' }, { cents: 999, label: '$9.99' }, { cents: 1499, label: '$14.99' }];

type StepStatus = 'idle' | 'running' | 'done' | 'error';
const STEPS = ['demand', 'research', 'taste_map', 'scorers'] as const;
const STEP_LABELS = ['Demand Estimate', 'Taste Research', 'Taste Map', 'Scorer Hypotheses'];

export default function CreateScorerPage() {
  const [goal, setGoal] = useState('');
  const [rawText, setRawText] = useState('');
  const [selectedSegments, setSelectedSegments] = useState<string[]>(['startup_founder_operator', 'marketing_growth_lead', 'creator_coach_consultant']);
  const [priceCents, setPriceCents] = useState(499);
  const [bestFor, setBestFor] = useState<string[]>([]);
  const [stepStatuses, setStepStatuses] = useState<StepStatus[]>(['idle', 'idle', 'idle', 'idle']);
  const [stepResults, setStepResults] = useState<(unknown | null)[]>([null, null, null, null]);
  const [stepErrors, setStepErrors] = useState<(string | null)[]>([null, null, null, null]);
  const [running, setRunning] = useState(false);

  function toggleSegment(id: string) { setSelectedSegments(prev => prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]); }
  function toggleContentJob(job: string) { setBestFor(prev => prev.includes(job) ? prev.filter(j => j !== job) : [...prev, job]); }

  async function callStep(stepIdx: number, previousResult: unknown): Promise<unknown | null> {
    setStepStatuses(prev => prev.map((s, i) => i === stepIdx ? 'running' : s));
    try {
      const res = await fetch('/api/create-scorer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          goal: goal.trim(), raw_text: rawText.trim(),
          target_segments: selectedSegments, price_cents: priceCents, best_for: bestFor,
          step: STEPS[stepIdx], previous_result: previousResult,
        }),
      });
      if (!res.ok) { const err = await res.json(); throw new Error(err.error || `HTTP ${res.status}`); }
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

  async function runPipeline() {
    if (!goal.trim()) return;
    setRunning(true);
    setStepStatuses(['idle', 'idle', 'idle', 'idle']);
    setStepResults([null, null, null, null]);
    setStepErrors([null, null, null, null]);

    let prev: unknown = null;
    for (let i = 0; i < 4; i++) {
      const result = await callStep(i, prev);
      if (!result) break;
      prev = result;
    }
    setRunning(false);
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
            Pick a goal, see estimated demand instantly, then watch Bedrock generate taste research and scorer hypotheses step by step.
          </p>
        </div>

        {/* Input Form */}
        <div className="glass-card p-6 mb-8">
          <div className="mb-6">
            <label className="text-sm font-medium mb-2 block">Dynamic Variable (goal)</label>
            <input type="text" value={goal} onChange={(e) => setGoal(e.target.value)} placeholder='"urgent", "trustworthy", "funny"' className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:border-brand-500 focus:outline-none" />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {GOAL_SUGGESTIONS.map(g => (
                <button key={g} onClick={() => setGoal(g)} className={`rounded-full px-3 py-1 text-xs transition ${goal === g ? 'bg-brand-600 text-white' : 'border border-white/10 text-white/50 hover:bg-white/5'}`}>{g}</button>
              ))}
            </div>
          </div>
          <div className="mb-6">
            <label className="text-sm font-medium mb-2 block">Sample text (optional)</label>
            <textarea value={rawText} onChange={(e) => setRawText(e.target.value)} placeholder="Paste text to improve..." rows={2} className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:border-brand-500 focus:outline-none resize-none" />
          </div>
          <div className="mb-6">
            <label className="text-sm font-medium mb-2 block">Target segments</label>
            <div className="flex flex-wrap gap-2">
              {SEGMENTS.map(seg => (
                <button key={seg.id} onClick={() => toggleSegment(seg.id)} className={`rounded-full px-3 py-1.5 text-xs transition ${selectedSegments.includes(seg.id) ? 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/30' : 'border border-white/10 text-white/50 hover:bg-white/5'}`}>{seg.label}</button>
              ))}
            </div>
          </div>
          <div className="mb-6">
            <label className="text-sm font-medium mb-2 block">Best for</label>
            <div className="flex flex-wrap gap-2">
              {CONTENT_JOBS.map(job => (
                <button key={job} onClick={() => toggleContentJob(job)} className={`rounded-full px-3 py-1.5 text-xs transition ${bestFor.includes(job) ? 'bg-brand-500/20 text-brand-300 ring-1 ring-brand-500/30' : 'border border-white/10 text-white/50 hover:bg-white/5'}`}>{job}</button>
              ))}
            </div>
          </div>
          <div className="mb-6">
            <label className="text-sm font-medium mb-2 block">Price</label>
            <div className="flex gap-2">
              {PRICE_OPTIONS.map(p => (
                <button key={p.cents} onClick={() => setPriceCents(p.cents)} className={`rounded-lg px-4 py-2 text-sm font-mono transition ${priceCents === p.cents ? 'bg-brand-600 text-white' : 'border border-white/10 text-white/50 hover:bg-white/5'}`}>{p.label}</button>
              ))}
            </div>
          </div>
          <button onClick={runPipeline} disabled={running || !goal.trim()} className="w-full rounded-lg bg-gradient-to-r from-brand-600 to-purple-600 py-3 text-sm font-medium text-white transition hover:from-brand-500 hover:to-purple-500 disabled:opacity-40 disabled:cursor-not-allowed">
            {running ? 'Running...' : 'Estimate Demand + Generate Scorer →'}
          </button>
        </div>

        {/* Pipeline Progress */}
        <div className={`mb-6 flex items-center justify-center gap-2 ${stepStatuses.every(s => s === 'idle') ? 'hidden' : ''}`}>
          {STEP_LABELS.map((label, i) => {
            const status = stepStatuses[i];
            let cls = 'bg-white/5 text-white/30 ring-1 ring-white/10';
            if (status === 'done') cls = 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20';
            else if (status === 'running') cls = 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20 animate-pulse';
            else if (status === 'error') cls = 'bg-red-500/10 text-red-400 ring-1 ring-red-500/20';
            return (
              <div key={i} className="flex items-center gap-2">
                <span className={`rounded-full px-3 py-1 text-xs font-medium ${cls}`}>{label}</span>
                {i < 3 && <span className="text-white/20 text-xs">→</span>}
              </div>
            );
          })}
        </div>

        {/* Step 1: Demand */}
        {stepResults[0] != null ? <DemandPanel data={stepResults[0]} /> : null}
        {stepErrors[0] != null ? <ErrorBox msg={stepErrors[0]} /> : null}

        {/* Step 2: Research */}
        {stepStatuses[1] === 'running' ? <LoadingBox label="Calling Bedrock for taste research..." /> : null}
        {stepResults[1] != null ? <ResearchPanel data={stepResults[1]} /> : null}
        {stepErrors[1] != null ? <ErrorBox msg={stepErrors[1]} /> : null}

        {/* Step 3: Taste Map */}
        {stepStatuses[2] === 'running' ? <LoadingBox label="Generating taste map..." /> : null}
        {stepResults[2] != null ? <TasteMapPanel data={stepResults[2]} /> : null}
        {stepErrors[2] != null ? <ErrorBox msg={stepErrors[2]} /> : null}

        {/* Step 4: Scorers */}
        {stepStatuses[3] === 'running' ? <LoadingBox label="Generating scorer hypotheses..." /> : null}
        {stepResults[3] != null ? <ScorersPanel data={stepResults[3]} /> : null}
        {stepErrors[3] != null ? <ErrorBox msg={stepErrors[3]} /> : null}
      </div>
    </div>
  );
}

function DemandPanel({ data }: { data: unknown }) {
  const d = data as { segment_demand: Array<{ label: string; reveal_probability: number; estimated_buyers_per_100: number }>; avg_conversion_rate: number; estimated_revenue_per_100_personas: number; estimated_platform_take: number };
  return (
    <div className="glass-card p-6 mb-6">
      <div className="flex items-center justify-between mb-4"><h2 className="text-lg font-semibold">Demand Estimate</h2><span className="badge-info">from Nemotron panel</span></div>
      <div className="grid gap-4 sm:grid-cols-3 mb-6">
        <div className="text-center"><div className="text-2xl font-bold text-emerald-400">{(d.avg_conversion_rate * 100).toFixed(0)}%</div><div className="text-xs text-white/40">Avg conversion</div></div>
        <div className="text-center"><div className="text-2xl font-bold">${d.estimated_revenue_per_100_personas.toFixed(0)}</div><div className="text-xs text-white/40">Revenue / 100</div></div>
        <div className="text-center"><div className="text-2xl font-bold text-brand-400">${d.estimated_platform_take.toFixed(0)}</div><div className="text-xs text-white/40">Platform take</div></div>
      </div>
      <div className="space-y-2">
        {d.segment_demand.map(seg => (
          <div key={seg.label} className="flex items-center gap-3">
            <span className="w-36 text-xs text-white/50 truncate">{seg.label}</span>
            <div className="flex-1 h-4 rounded-full bg-white/[0.04] overflow-hidden">
              <div className="h-full rounded-full bg-gradient-to-r from-brand-600 to-emerald-500 opacity-70" style={{ width: `${seg.reveal_probability * 100}%` }} />
            </div>
            <span className="w-12 text-right text-xs font-mono text-white/50">{seg.estimated_buyers_per_100}/100</span>
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
      <h2 className="text-lg font-semibold mb-4">Taste Research</h2>
      <div className="space-y-4 text-sm text-white/60">
        {Object.entries(d).map(([key, val]) => (
          <div key={key}><div className="text-xs font-medium text-white/40 uppercase mb-1">{key.replace(/_/g, ' ')}</div><p className="leading-relaxed">{String(val).slice(0, 400)}</p></div>
        ))}
      </div>
    </div>
  );
}

function TasteMapPanel({ data }: { data: unknown }) {
  const d = data as Record<string, unknown>;
  return (
    <div className="glass-card p-6 mb-6">
      <h2 className="text-lg font-semibold mb-4">Taste Map</h2>
      <div className="grid gap-4 sm:grid-cols-3">
        {(['rewards', 'punishes', 'preserves'] as const).map(key => {
          const items = d[key];
          if (!Array.isArray(items)) return null;
          const colors = { rewards: 'text-emerald-400', punishes: 'text-red-400', preserves: 'text-amber-400' };
          return (
            <div key={key}><div className={`text-xs font-medium uppercase mb-2 ${colors[key]}`}>{key}</div><ul className="space-y-1">{items.map((item, i) => <li key={i} className="text-sm text-white/60">• {String(item)}</li>)}</ul></div>
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
      <h2 className="text-lg font-semibold mb-4">Generated Scorer Hypotheses</h2>
      <div className="space-y-4">
        {scorers.map((s: Record<string, unknown>, i: number) => (
          <div key={i} className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold">{String(s.name || `Scorer ${i + 1}`)}</span>
            </div>
            {s.mechanism ? <p className="text-sm text-white/50 mb-2">{String(s.mechanism)}</p> : null}
            {s.formula_sketch ? <div className="rounded-md bg-black/40 border border-white/[0.06] px-3 py-2 font-mono text-xs text-white/50">{String(s.formula_sketch)}</div> : null}
            {Array.isArray(s.expected_segments) && (
              <div className="mt-2 flex flex-wrap gap-1">{(s.expected_segments as string[]).map((seg: string) => <span key={seg} className="rounded-full bg-brand-500/10 px-2 py-0.5 text-[10px] text-brand-300">{seg}</span>)}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function LoadingBox({ label }: { label: string }) {
  return <div className="glass-card p-4 mb-6 text-sm text-amber-400 animate-pulse">⟳ {label}</div>;
}

function ErrorBox({ msg }: { msg: string }) {
  return <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-400">{msg}</div>;
}
