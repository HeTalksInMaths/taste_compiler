'use client';

import { useState } from 'react';
import Link from 'next/link';

type StageStatus = 'idle' | 'running' | 'done' | 'error';

interface StageState {
  status: StageStatus;
  data: unknown;
  searchResults?: Array<{ title: string; url: string; snippet: string }>;
  error?: string;
}

const STAGE_META = [
  { label: 'Causal Research', num: 1, desc: 'Search for causal factors, then synthesize with LLM' },
  { label: 'Causal Graph', num: 2, desc: 'Build node/edge graph from research' },
  { label: 'Measurement Research', num: 3, desc: 'Search NLP methods, then map nodes to text features' },
  { label: 'Scorer Hypotheses', num: 4, desc: 'Generate scoring functions with code' },
  { label: 'Pair Generation', num: 5, desc: 'Search real content, generate pos/neg evaluation pairs' },
  { label: 'Scorer Evaluation', num: 6, desc: 'Run scorers on pairs, compute Pareto frontier' },
  { label: 'Failure Packet', num: 7, desc: 'Analyze failures, generate repair instructions' },
  { label: 'Repair Scorers', num: 8, desc: 'Generate evolved scorers targeting failure patterns' },
];

const VARIABLES = ['trustworthy', 'persuasive', 'concise', 'urgent', 'funny', 'professional', 'empathetic', 'data-driven'];

export default function StagesPage() {
  const [targetVariable, setTargetVariable] = useState('trustworthy');
  const [stages, setStages] = useState<StageState[]>(Array(8).fill(null).map(() => ({ status: 'idle', data: null })));
  const [allOutputs, setAllOutputs] = useState<Record<string, unknown>>({});
  const [currentStage, setCurrentStage] = useState(0);
  const [running, setRunning] = useState(false);
  const [expandedStages, setExpandedStages] = useState<Set<number>>(new Set());

  function toggleExpand(idx: number) {
    setExpandedStages(prev => {
      const next = new Set(prev);
      next.has(idx) ? next.delete(idx) : next.add(idx);
      return next;
    });
  }

  async function runStage(stageNum: number, previousOutput: unknown, outputs: Record<string, unknown>) {
    setStages(prev => prev.map((s, i) => i === stageNum ? { status: 'running', data: null } : s));
    try {
      const res = await fetch('/api/stages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_variable: targetVariable,
          stage: stageNum + 1,
          previous_output: previousOutput,
          all_outputs: outputs,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        const errMsg = typeof err.error === 'string' ? err.error : JSON.stringify(err.error) || `HTTP ${res.status}`;
        throw new Error(errMsg);
      }
      const { result, search_results } = await res.json();
      setStages(prev => prev.map((s, i) => i === stageNum ? { status: 'done', data: result, searchResults: search_results } : s));
      return result;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error';
      setStages(prev => prev.map((s, i) => i === stageNum ? { status: 'error', data: null, error: msg } : s));
      return null;
    }
  }

  async function runAll() {
    setRunning(true);
    setStages(Array(8).fill(null).map(() => ({ status: 'idle', data: null })));
    setExpandedStages(new Set());
    const outputs: Record<string, unknown> = {};
    let prevOutput: unknown = null;
    for (let i = 0; i < 8; i++) {
      setCurrentStage(i);
      const result = await runStage(i, prevOutput, outputs);
      if (!result) break;
      outputs[`stage${i + 1}`] = result;
      setAllOutputs({ ...outputs });
      prevOutput = result;
    }
    setRunning(false);
  }

  const pipelineDone = stages.every(s => s.status === 'done');

  return (
    <main className="px-6 py-12">
      <div className="mx-auto max-w-4xl">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">Live Pipeline Proof</h1>
          <p className="mt-2 text-sm" style={{ color: 'rgba(255,255,255,0.5)' }}>
            This is the agent loop behind each scorer artifact: research, taste map, scorer generation,
            pair testing, evaluation, failure analysis, and repair.
          </p>
        </div>

        {/* Config */}
        <div className="glass-card p-5 mb-6">
          <label className="text-xs font-medium mb-3 block" style={{ color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Quality Target</label>
          <div className="flex flex-wrap gap-2 mb-4">
            {VARIABLES.map(v => (
              <button
                key={v}
                onClick={() => !running && setTargetVariable(v)}
                className="rounded-full px-3 py-1.5 text-xs transition"
                style={targetVariable === v ? { backgroundColor: '#4c6ef5', color: 'white' } : { border: '1px solid rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.5)' }}
              >
                {v}
              </button>
            ))}
          </div>
          <button
            onClick={runAll}
            disabled={running}
            className="rounded-lg px-6 py-2.5 text-sm font-medium text-white transition"
            style={{ background: 'linear-gradient(to right, #4c6ef5, #7c3aed)', opacity: running ? 0.5 : 1, cursor: running ? 'not-allowed' : 'pointer' }}
          >
            {running ? `Running Stage ${currentStage + 1}/8...` : 'Run Taste Compiler Pipeline →'}
          </button>
        </div>

        {/* Pipeline Progress Badges */}
        {!stages.every(s => s.status === 'idle') && (
          <div className="flex flex-wrap items-center gap-2 mb-6">
            {STAGE_META.map((meta, i) => {
              const status = stages[i].status;
              const color = status === 'done' ? 'rgba(16,185,129,0.15)' : status === 'running' ? 'rgba(245,158,11,0.15)' : status === 'error' ? 'rgba(248,113,113,0.15)' : 'rgba(255,255,255,0.03)';
              const text = status === 'done' ? 'rgb(52,211,153)' : status === 'running' ? 'rgb(251,191,36)' : status === 'error' ? 'rgb(248,113,113)' : 'rgba(255,255,255,0.3)';
              return (
                <div key={i} className="flex items-center gap-1.5">
                  <span className="rounded-full px-2.5 py-1 text-[10px] font-medium" style={{ backgroundColor: color, color: text }}>
                    {status === 'done' ? '✓' : status === 'running' ? '⟳' : status === 'error' ? '✗' : '○'} {meta.num}
                  </span>
                  {i < 7 && <span className="text-[10px]" style={{ color: 'rgba(255,255,255,0.15)' }}>→</span>}
                </div>
              );
            })}
          </div>
        )}

        {/* Stage Results — Collapsed with summaries */}
        {stages.map((stage, i) => {
          if (stage.status === 'idle') return null;
          const meta = STAGE_META[i];
          const expanded = expandedStages.has(i);

          if (stage.status === 'running') return (
            <div key={i} className="glass-card p-4 mb-3 animate-pulse">
              <span className="text-sm" style={{ color: 'rgb(251,191,36)' }}>Stage {meta.num} — {meta.label}...</span>
            </div>
          );

          if (stage.status === 'error') return (
            <div key={i} className="rounded-lg p-4 mb-3" style={{ border: '1px solid rgba(248,113,113,0.2)', backgroundColor: 'rgba(248,113,113,0.05)' }}>
              <span className="text-sm font-medium" style={{ color: 'rgb(248,113,113)' }}>Stage {meta.num} — {meta.label}</span>
              <p className="text-xs mt-1" style={{ color: 'rgba(248,113,113,0.7)' }}>{stage.error}</p>
            </div>
          );

          const summary = getStageSummary(i, stage);

          return (
            <div key={i} className="glass-card mb-3 overflow-hidden">
              <div
                className="flex items-center justify-between p-4 cursor-pointer"
                onClick={() => toggleExpand(i)}
              >
                <div className="flex items-center gap-3">
                  <span className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ backgroundColor: 'rgba(16,185,129,0.15)', color: 'rgb(52,211,153)' }}>✓ {meta.num}</span>
                  <span className="text-sm font-medium text-white">{meta.label}</span>
                  <span className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>{summary}</span>
                </div>
                <span className="text-xs" style={{ color: 'rgba(255,255,255,0.3)' }}>{expanded ? '▾' : '▸'}</span>
              </div>
              {expanded && (
                <div className="px-4 pb-4 pt-0" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                  {stage.searchResults && stage.searchResults.length > 0 && (
                    <div className="mb-3 p-3 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
                      <div className="text-[10px] uppercase mb-2" style={{ color: 'rgba(245,158,11,0.8)', letterSpacing: '0.05em' }}>Search Results ({stage.searchResults.length})</div>
                      {stage.searchResults.slice(0, 5).map((r, j) => (
                        <div key={j} className="text-xs mb-1">
                          <a href={r.url} target="_blank" rel="noopener" style={{ color: 'rgb(52,211,153)', textDecoration: 'none' }}>{r.title || r.url}</a>
                          {r.snippet && <span style={{ color: 'rgba(255,255,255,0.3)', marginLeft: 4 }}>— {r.snippet.slice(0, 60)}</span>}
                        </div>
                      ))}
                    </div>
                  )}
                  {i === 0 && <Stage1Content data={stage.data} />}
                  {i === 1 && <Stage2Content data={stage.data} />}
                  {i === 2 && <Stage3Content data={stage.data} />}
                  {i === 3 && <Stage4Content data={stage.data} />}
                  {i === 4 && <Stage5Content data={stage.data} />}
                  {i === 5 && <Stage6Content data={stage.data} />}
                  {i === 6 && <Stage7Content data={stage.data} />}
                  {i === 7 && <Stage8Content data={stage.data} />}
                </div>
              )}
            </div>
          );
        })}

        {/* What this proves + CTAs */}
        {pipelineDone && (
          <>
            <div className="glass-card p-5 mb-4 mt-6">
              <div className="text-sm font-semibold text-white mb-2">What this proves</div>
              <p className="text-xs leading-relaxed" style={{ color: 'rgba(255,255,255,0.5)' }}>
                The system generated scorer hypotheses, tested them on positive/negative pairs,
                found failures, and repaired the scorer logic — all grounded in real research from Exa search.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-3">
              <Link href="/create" className="flex-1 rounded-lg px-5 py-3 text-center text-sm font-medium transition" style={{ background: 'linear-gradient(to right, #4c6ef5, #7c3aed)', color: 'white' }}>
                Create a scorer from reference text →
              </Link>
              <Link href="/market-dynamics" className="flex-1 rounded-lg px-5 py-3 text-center text-sm font-medium transition" style={{ border: '1px solid rgba(255,255,255,0.15)', color: 'rgba(255,255,255,0.7)' }}>
                Market-test this scorer →
              </Link>
            </div>
          </>
        )}
      </div>
    </main>
  );
}

function getStageSummary(idx: number, state: StageState): string {
  const d = state.data as Record<string, unknown>;
  if (!d) return '';
  switch (idx) {
    case 0: return `${(d.causal_research as unknown[])?.length || 0} causal factors from ${state.searchResults?.length || 0} sources`;
    case 1: return `${(d.causal_nodes as unknown[])?.length || 0} nodes, ${(d.causal_edges as unknown[])?.length || 0} edges`;
    case 2: return `${(d.measurement_research as unknown[])?.length || 0} measurement methods`;
    case 3: return `${(d.scorers as unknown[])?.length || 0} scorer hypotheses`;
    case 4: return `${(d.pairs as unknown[])?.length || 0} evaluation pairs`;
    case 5: { const s = d.summary as { total_evaluated?: number; pareto_size?: number }; return `${s?.total_evaluated || 0} evaluated, ${s?.pareto_size || 0} on Pareto`; }
    case 6: return `${(d.failure_patterns as unknown[])?.length || 0} failures, ${(d.mutation_instructions as unknown[])?.length || 0} repairs`;
    case 7: return `${(d.repair_scorers as unknown[])?.length || 0} repair scorers`;
    default: return '';
  }
}

function Stage1Content({ data }: { data: unknown }) {
  const d = data as { causal_research?: Array<{ claim: string; causal_variable: string; effect_direction: string; mechanism: string }>; research_tensions?: Array<{ claim: string }> };
  return (
    <div className="space-y-2">
      {d.causal_research?.map((item, i) => (
        <div key={i} className="pl-3" style={{ borderLeft: `2px solid ${item.effect_direction === 'increases' ? 'rgb(52,211,153)' : item.effect_direction === 'decreases' ? 'rgb(248,113,113)' : 'rgb(251,191,36)'}` }}>
          <div className="text-xs"><span className="font-semibold text-white">{item.causal_variable}</span> <span className="opacity-60">{item.effect_direction}</span></div>
          <div className="text-[11px]" style={{ color: 'rgba(255,255,255,0.4)' }}>{item.claim}</div>
          {item.mechanism && <div className="text-[10px] italic" style={{ color: 'rgba(255,255,255,0.3)' }}>↳ {item.mechanism}</div>}
        </div>
      ))}
      {d.research_tensions && d.research_tensions.length > 0 && (
        <div className="pt-2 mt-2" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          {d.research_tensions.map((t, i) => <div key={i} className="text-[11px]" style={{ color: 'rgb(251,191,36)' }}>⚡ {t.claim}</div>)}
        </div>
      )}
    </div>
  );
}

function Stage2Content({ data }: { data: unknown }) {
  const d = data as { causal_nodes?: Array<{ label: string; role: string }>; causal_edges?: Array<{ from: string; to: string; relationship: string }>; summary_theory?: string };
  return (
    <div>
      {d.summary_theory && <p className="text-xs leading-relaxed mb-3" style={{ color: 'rgba(255,255,255,0.6)' }}>{d.summary_theory}</p>}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-[10px] uppercase mb-2" style={{ color: 'rgba(255,255,255,0.3)', letterSpacing: '0.05em' }}>Nodes ({d.causal_nodes?.length})</div>
          {d.causal_nodes?.map((n, i) => (
            <div key={i} className="text-xs mb-1 pl-2" style={{ borderLeft: '2px solid rgba(255,255,255,0.06)' }}>
              <span className="text-white font-medium">{n.label}</span> <span style={{ color: 'rgba(255,255,255,0.3)' }}>{n.role}</span>
            </div>
          ))}
        </div>
        <div>
          <div className="text-[10px] uppercase mb-2" style={{ color: 'rgba(255,255,255,0.3)', letterSpacing: '0.05em' }}>Edges ({d.causal_edges?.length})</div>
          {d.causal_edges?.map((e, i) => (
            <div key={i} className="text-xs mb-1">{e.from} → {e.to} <span style={{ color: 'rgba(255,255,255,0.3)' }}>({e.relationship})</span></div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stage3Content({ data }: { data: unknown }) {
  const d = data as { measurement_research?: Array<{ causal_node: string; measurement_claim: string; text_features: string[]; implementation_ideas: string[] }> };
  return (
    <div className="space-y-3">
      {d.measurement_research?.map((m, i) => (
        <div key={i} className="pl-3" style={{ borderLeft: '2px solid rgb(251,191,36)' }}>
          <div className="text-xs font-medium text-white">{m.causal_node}</div>
          <div className="text-[11px]" style={{ color: 'rgba(255,255,255,0.5)' }}>{m.measurement_claim}</div>
          <div className="text-[10px] mt-1" style={{ color: 'rgba(255,255,255,0.3)' }}>features: {m.text_features?.join(', ')}</div>
        </div>
      ))}
    </div>
  );
}

function Stage4Content({ data }: { data: unknown }) {
  const d = data as { scorers?: Array<{ scorer_id: string; hypothesis: string; functional_form: string; code: string }> };
  return (
    <div className="space-y-2">
      {d.scorers?.map((s, i) => (
        <div key={i} className="p-3 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs font-semibold text-white">{s.scorer_id}</span>
            <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(251,191,36,0.1)', color: 'rgb(251,191,36)' }}>{s.functional_form}</span>
          </div>
          <div className="text-[11px]" style={{ color: 'rgba(255,255,255,0.5)' }}>{s.hypothesis}</div>
          {s.code && (
            <details className="mt-2">
              <summary className="text-[10px] cursor-pointer" style={{ color: 'rgb(52,211,153)' }}>View code</summary>
              <pre className="text-[10px] mt-2 p-2 rounded overflow-auto max-h-32" style={{ color: 'rgba(255,255,255,0.4)', backgroundColor: 'rgba(0,0,0,0.3)', whiteSpace: 'pre-wrap' }}>{s.code}</pre>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}

function Stage5Content({ data }: { data: unknown }) {
  const d = data as { pairs?: Array<{ pair_id: string; anchor: string; positive: string; negative: string; split: string; causal_nodes_tested: string[] }> };
  return (
    <div className="space-y-2">
      {d.pairs?.map((p, i) => (
        <div key={i} className="p-3 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
          <div className="flex justify-between mb-2">
            <span className="text-[11px] font-medium text-white">{p.pair_id}</span>
            <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.4)' }}>{p.split || 'train'}</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="text-[11px] p-2 rounded" style={{ backgroundColor: 'rgba(16,185,129,0.05)', border: '1px solid rgba(16,185,129,0.15)' }}>
              <span className="text-[9px] block mb-1" style={{ color: 'rgb(52,211,153)' }}>POSITIVE</span>{p.positive?.slice(0, 80)}
            </div>
            <div className="text-[11px] p-2 rounded" style={{ backgroundColor: 'rgba(248,113,113,0.05)', border: '1px solid rgba(248,113,113,0.15)' }}>
              <span className="text-[9px] block mb-1" style={{ color: 'rgb(248,113,113)' }}>NEGATIVE</span>{p.negative?.slice(0, 80)}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function Stage6Content({ data }: { data: unknown }) {
  const d = data as { scorer_evaluations?: Array<{ scorer_id: string; heldout_accuracy: number; heldout_mean_gap: number; eligible: boolean; pareto_member: boolean }>; summary?: { total_evaluated: number; eligible: number; pareto_size: number } };
  return (
    <div>
      {d.summary && (
        <div className="flex gap-4 mb-3">
          <div className="text-center"><div className="text-lg font-bold text-white">{d.summary.total_evaluated}</div><div className="text-[10px]" style={{ color: 'rgba(255,255,255,0.4)' }}>Evaluated</div></div>
          <div className="text-center"><div className="text-lg font-bold" style={{ color: 'rgb(52,211,153)' }}>{d.summary.eligible}</div><div className="text-[10px]" style={{ color: 'rgba(255,255,255,0.4)' }}>Eligible</div></div>
          <div className="text-center"><div className="text-lg font-bold" style={{ color: 'rgb(145,167,255)' }}>{d.summary.pareto_size}</div><div className="text-[10px]" style={{ color: 'rgba(255,255,255,0.4)' }}>Pareto</div></div>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead><tr style={{ color: 'rgba(255,255,255,0.4)' }}><th className="text-left py-1">Scorer</th><th className="text-left">Accuracy</th><th className="text-left">Gap</th><th className="text-left">Eligible</th><th className="text-left">Pareto</th></tr></thead>
          <tbody>
            {d.scorer_evaluations?.map((e, i) => (
              <tr key={i} className="text-[11px]" style={{ color: 'rgba(255,255,255,0.6)' }}>
                <td className="py-1 font-medium text-white">{e.scorer_id}</td>
                <td>{(e.heldout_accuracy * 100).toFixed(0)}%</td>
                <td>{e.heldout_mean_gap?.toFixed(2)}</td>
                <td>{e.eligible ? <span style={{ color: 'rgb(52,211,153)' }}>✓</span> : <span style={{ color: 'rgb(248,113,113)' }}>✗</span>}</td>
                <td>{e.pareto_member ? <span style={{ color: 'rgb(145,167,255)' }}>★</span> : '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stage7Content({ data }: { data: unknown }) {
  const d = data as { failure_patterns?: Array<{ pattern_id: string; reasoning_error: string; severity: string }>; mutation_instructions?: Array<{ instruction_id: string; instruction: string; targets_failure_patterns: string[] }> };
  return (
    <div>
      <div className="space-y-2 mb-3">
        {d.failure_patterns?.map((fp, i) => (
          <div key={i} className="pl-3" style={{ borderLeft: `2px solid ${fp.severity === 'high' ? 'rgb(248,113,113)' : fp.severity === 'medium' ? 'rgb(251,191,36)' : 'rgba(255,255,255,0.2)'}` }}>
            <div className="text-xs"><span className="font-medium text-white">{fp.pattern_id}</span> <span className="text-[10px]" style={{ color: fp.severity === 'high' ? 'rgb(248,113,113)' : 'rgb(251,191,36)' }}>{fp.severity}</span></div>
            <div className="text-[11px]" style={{ color: 'rgba(255,255,255,0.5)' }}>{fp.reasoning_error}</div>
          </div>
        ))}
      </div>
      {d.mutation_instructions && d.mutation_instructions.length > 0 && (
        <details>
          <summary className="text-[10px] cursor-pointer" style={{ color: 'rgb(52,211,153)' }}>Repair instructions ({d.mutation_instructions.length})</summary>
          <div className="mt-2 space-y-1">
            {d.mutation_instructions.map((mi, i) => (
              <div key={i} className="text-[11px]" style={{ color: 'rgba(255,255,255,0.5)' }}>
                <span style={{ color: 'rgba(255,255,255,0.3)' }}>{mi.instruction_id}:</span> {mi.instruction}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function Stage8Content({ data }: { data: unknown }) {
  const d = data as { repair_scorers?: Array<{ scorer_id: string; hypothesis: string; functional_form: string; repair_strategy: string; targets_failure_patterns: string[]; code: string }> };
  return (
    <div className="space-y-2">
      {d.repair_scorers?.map((s, i) => (
        <div key={i} className="p-3 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs font-semibold text-white">{s.scorer_id}</span>
            <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(16,185,129,0.1)', color: 'rgb(52,211,153)' }}>{s.functional_form}</span>
          </div>
          <div className="text-[11px]" style={{ color: 'rgba(255,255,255,0.5)' }}>{s.hypothesis}</div>
          {s.repair_strategy && <div className="text-[10px] mt-1" style={{ color: 'rgb(251,191,36)' }}>strategy: {s.repair_strategy}</div>}
          {s.targets_failure_patterns && <div className="text-[9px]" style={{ color: 'rgba(255,255,255,0.3)' }}>targets: {s.targets_failure_patterns.join(', ')}</div>}
          {s.code && (
            <details className="mt-2">
              <summary className="text-[10px] cursor-pointer" style={{ color: 'rgb(52,211,153)' }}>View code</summary>
              <pre className="text-[10px] mt-2 p-2 rounded overflow-auto max-h-32" style={{ color: 'rgba(255,255,255,0.4)', backgroundColor: 'rgba(0,0,0,0.3)', whiteSpace: 'pre-wrap' }}>{s.code}</pre>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}
