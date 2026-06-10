'use client';

import { useState } from 'react';

type StageStatus = 'idle' | 'running' | 'done' | 'error';

interface StageState {
  status: StageStatus;
  data: unknown;
  searchResults?: Array<{ title: string; url: string; snippet: string }>;
  error?: string;
}

const STAGE_META = [
  { label: 'Causal Research', num: 1, source: 'exa+llm', desc: 'Search for causal factors, then synthesize with LLM' },
  { label: 'Causal Graph', num: 2, source: 'llm', desc: 'Build node/edge graph from research' },
  { label: 'Measurement Research', num: 3, source: 'exa+llm', desc: 'Search NLP methods, then map nodes to text features' },
  { label: 'Scorer Hypotheses', num: 4, source: 'llm', desc: 'Generate scoring functions with code' },
  { label: 'Pair Generation', num: 5, source: 'exa+llm', desc: 'Search real content, generate pos/neg evaluation pairs' },
  { label: 'Scorer Evaluation', num: 6, source: 'deterministic', desc: 'Run scorers on pairs, compute Pareto frontier' },
  { label: 'Failure Packet', num: 7, source: 'llm', desc: 'Analyze failures, generate repair instructions' },
  { label: 'Repair Scorers', num: 8, source: 'llm', desc: 'Generate evolved scorers targeting failure patterns' },
];

const VARIABLES = ['trustworthy', 'persuasive', 'concise', 'urgent', 'funny', 'professional', 'empathetic', 'data-driven'];

export default function StagesPage() {
  const [targetVariable, setTargetVariable] = useState('trustworthy');
  const [stages, setStages] = useState<StageState[]>(Array(8).fill(null).map(() => ({ status: 'idle', data: null })));
  const [allOutputs, setAllOutputs] = useState<Record<string, unknown>>({});
  const [currentStage, setCurrentStage] = useState(0);
  const [running, setRunning] = useState(false);

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
        throw new Error(err.error || `HTTP ${res.status}`);
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

  return (
    <main className="run-page">
      <div className="run-header">
        <h1 className="run-id">Stages 1–8 Live Pipeline</h1>
        <p className="run-raw-text">
          Causal Research → Graph → Measurement → Scorers → Pairs → Eval → Failure → Repair
        </p>
      </div>

      {/* Config */}
      <div className="panel">
        <div className="panel-header">Configuration</div>
        <div className="form-group" style={{ marginBottom: 16 }}>
          <label className="form-label">Target Variable</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 6 }}>
            {VARIABLES.map(v => (
              <button
                key={v}
                onClick={() => !running && setTargetVariable(v)}
                className={`btn ${targetVariable === v ? 'btn-primary' : ''}`}
                style={{ padding: '6px 14px', fontSize: 12 }}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
        <button onClick={runAll} disabled={running} className="btn btn-primary" style={{ opacity: running ? 0.5 : 1 }}>
          {running ? `Running Stage ${currentStage + 1}/8...` : 'Run Full Pipeline (8 Stages) →'}
        </button>
      </div>

      {/* Pipeline Progress */}
      <div className="panel">
        <div className="panel-header">Pipeline Progress</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 4 }}>
          {STAGE_META.map((meta, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span className={`badge-${getBadgeColor(stages[i].status)}`} style={{ whiteSpace: 'nowrap' }}>
                {stages[i].status === 'running' ? '⟳' : stages[i].status === 'done' ? '✓' : stages[i].status === 'error' ? '✗' : '○'} {meta.num}
              </span>
              {i < 7 && <span style={{ color: 'var(--fg-muted)', fontSize: 10 }}>→</span>}
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
          {STAGE_META.map((meta, i) => (
            <div key={i} style={{ fontSize: 10, color: stages[i].status === 'done' ? 'var(--green)' : 'var(--fg-muted)' }}>
              <strong>S{meta.num}</strong> {meta.label}
              <br /><span style={{ opacity: 0.6 }}>
                {meta.source === 'exa+llm' ? '🔍+🤖' : meta.source === 'llm' ? '🤖' : '⚙️'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Stage Outputs */}
      {stages.map((stage, i) => {
        if (stage.status === 'idle') return null;
        return <StagePanel key={i} stageNum={i + 1} meta={STAGE_META[i]} state={stage} />;
      })}
    </main>
  );
}

function getBadgeColor(status: StageStatus): string {
  if (status === 'done') return 'green';
  if (status === 'running') return 'amber';
  if (status === 'error') return 'red';
  return 'gray';
}

function StagePanel({ stageNum, meta, state }: { stageNum: number; meta: typeof STAGE_META[0]; state: StageState }) {
  if (state.status === 'running') return (
    <div className="panel">
      <div className="panel-header">Stage {stageNum} — {meta.label}</div>
      <div style={{ fontSize: 13, color: 'var(--amber)' }}>
        {meta.source === 'exa+llm' ? '🔍 Searching web + 🤖 Calling Bedrock...' : meta.source === 'deterministic' ? '⚙️ Computing...' : '🤖 Calling Bedrock...'}
      </div>
    </div>
  );
  if (state.status === 'error') return (
    <div className="panel error-panel">
      <div className="panel-header">Stage {stageNum} — {meta.label} — Error</div>
      <div style={{ fontSize: 13, color: 'var(--red)' }}>{state.error}</div>
    </div>
  );
  if (!state.data) return null;

  return (
    <div className="panel">
      <div className="panel-header">
        Stage {stageNum} — {meta.label}
        <span style={{ float: 'right', fontSize: 10, opacity: 0.5 }}>
          {meta.source === 'exa+llm' ? '🔍 search + 🤖 LLM' : meta.source === 'llm' ? '🤖 LLM' : '⚙️ deterministic'}
        </span>
      </div>

      {/* Search Results (if any) */}
      {state.searchResults && state.searchResults.length > 0 && (
        <div style={{ marginBottom: 12, padding: 8, background: 'var(--bg)', border: '1px solid var(--panel-border)', borderRadius: 4 }}>
          <div style={{ fontSize: 10, color: 'var(--amber)', textTransform: 'uppercase', marginBottom: 4 }}>🔍 Exa Search Results ({state.searchResults.length})</div>
          {state.searchResults.slice(0, 5).map((r, i) => (
            <div key={i} style={{ fontSize: 11, marginBottom: 3 }}>
              <a href={r.url} target="_blank" rel="noopener" style={{ color: 'var(--green)', textDecoration: 'none' }}>{r.title || r.url}</a>
              {r.snippet && <span style={{ color: 'var(--fg-muted)', marginLeft: 4 }}>— {r.snippet.slice(0, 60)}</span>}
            </div>
          ))}
        </div>
      )}

      {/* Stage-specific rendering */}
      {stageNum === 1 && <Stage1Content data={state.data} />}
      {stageNum === 2 && <Stage2Content data={state.data} />}
      {stageNum === 3 && <Stage3Content data={state.data} />}
      {stageNum === 4 && <Stage4Content data={state.data} />}
      {stageNum === 5 && <Stage5Content data={state.data} />}
      {stageNum === 6 && <Stage6Content data={state.data} />}
      {stageNum === 7 && <Stage7Content data={state.data} />}
      {stageNum === 8 && <Stage8Content data={state.data} />}
    </div>
  );
}

function Stage1Content({ data }: { data: unknown }) {
  const d = data as { causal_research?: Array<{ claim: string; causal_variable: string; effect_direction: string; mechanism: string }>; research_tensions?: Array<{ claim: string }> };
  return (
    <div>
      {d.causal_research?.map((item, i) => (
        <div key={i} style={{ paddingLeft: 8, borderLeft: `2px solid ${item.effect_direction === 'increases' ? 'var(--green)' : item.effect_direction === 'decreases' ? 'var(--red)' : 'var(--amber)'}`, marginBottom: 6 }}>
          <div style={{ fontSize: 12 }}><strong>{item.causal_variable}</strong> <span className={`badge-${item.effect_direction === 'increases' ? 'green' : item.effect_direction === 'decreases' ? 'red' : 'amber'}`}>{item.effect_direction}</span></div>
          <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>{item.claim}</div>
          {item.mechanism && <div style={{ fontSize: 10, color: 'var(--fg-muted)', fontStyle: 'italic' }}>↳ {item.mechanism}</div>}
        </div>
      ))}
      {d.research_tensions && d.research_tensions.length > 0 && (
        <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--panel-border)', fontSize: 11, color: 'var(--amber)' }}>
          {d.research_tensions.map((t, i) => <div key={i}>⚡ {t.claim}</div>)}
        </div>
      )}
    </div>
  );
}

function Stage2Content({ data }: { data: unknown }) {
  const d = data as { causal_nodes?: Array<{ label: string; role: string; mechanism: string }>; causal_edges?: Array<{ from: string; to: string; relationship: string }>; summary_theory?: string };
  return (
    <div>
      {d.summary_theory && <div style={{ fontSize: 12, color: 'var(--fg)', marginBottom: 10, lineHeight: 1.5 }}>{d.summary_theory}</div>}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div>
          <div style={{ fontSize: 10, color: 'var(--fg-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Nodes ({d.causal_nodes?.length})</div>
          {d.causal_nodes?.slice(0, 8).map((n, i) => (
            <div key={i} style={{ fontSize: 11, marginBottom: 4, paddingLeft: 6, borderLeft: '2px solid var(--panel-border)' }}>
              <strong>{n.label}</strong> <span className={`badge-${n.role === 'increases' ? 'green' : n.role === 'decreases' ? 'red' : 'amber'}`}>{n.role}</span>
            </div>
          ))}
        </div>
        <div>
          <div style={{ fontSize: 10, color: 'var(--fg-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Edges ({d.causal_edges?.length})</div>
          {d.causal_edges?.slice(0, 8).map((e, i) => (
            <div key={i} style={{ fontSize: 11, marginBottom: 3 }}>
              <span style={{ color: 'var(--green)' }}>{e.from}</span> → <span style={{ color: 'var(--green)' }}>{e.to}</span>
              <span style={{ color: 'var(--fg-muted)', fontSize: 10 }}> ({e.relationship})</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stage3Content({ data }: { data: unknown }) {
  const d = data as { measurement_research?: Array<{ causal_node: string; measurement_claim: string; text_features: string[]; implementation_ideas: string[] }> };
  return (
    <div>
      {d.measurement_research?.map((m, i) => (
        <div key={i} style={{ paddingLeft: 8, borderLeft: '2px solid var(--amber)', marginBottom: 8 }}>
          <div style={{ fontSize: 12 }}><strong>{m.causal_node}</strong></div>
          <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>{m.measurement_claim}</div>
          <div style={{ fontSize: 10, color: 'var(--fg-muted)', marginTop: 2 }}>features: {m.text_features?.join(', ')}</div>
          <div style={{ fontSize: 10, color: 'var(--green)', marginTop: 1 }}>→ {m.implementation_ideas?.slice(0, 3).join(' | ')}</div>
        </div>
      ))}
    </div>
  );
}

function Stage4Content({ data }: { data: unknown }) {
  const d = data as { scorers?: Array<{ scorer_id: string; hypothesis: string; functional_form: string; causal_nodes_used: string[]; code: string }> };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {d.scorers?.map((s, i) => (
        <div key={i} style={{ padding: 10, background: 'var(--bg)', border: '1px solid var(--panel-border)', borderRadius: 4 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 12, fontWeight: 600 }}>{s.scorer_id}</span>
            <span className="badge-amber">{s.functional_form}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--fg)', lineHeight: 1.4 }}>{s.hypothesis}</div>
          {s.code && (
            <details style={{ marginTop: 4 }}>
              <summary style={{ fontSize: 10, color: 'var(--green)', cursor: 'pointer' }}>code</summary>
              <pre style={{ fontSize: 10, color: 'var(--fg-muted)', marginTop: 4, padding: 6, overflow: 'auto', maxHeight: 150, whiteSpace: 'pre-wrap' }}>{s.code}</pre>
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {d.pairs?.map((p, i) => (
        <div key={i} style={{ padding: 10, background: 'var(--bg)', border: '1px solid var(--panel-border)', borderRadius: 4 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 600 }}>{p.pair_id}</span>
            <span className={`badge-${p.split === 'heldout' ? 'amber' : 'gray'}`}>{p.split || 'train'}</span>
          </div>
          {p.anchor && <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginBottom: 4 }}>📌 {p.anchor.slice(0, 80)}</div>}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <div style={{ fontSize: 11, padding: 6, background: 'var(--green-bg)', borderRadius: 3, border: '1px solid var(--green)' }}>
              <span style={{ fontSize: 9, color: 'var(--green)' }}>POSITIVE</span><br />{p.positive?.slice(0, 80)}
            </div>
            <div style={{ fontSize: 11, padding: 6, background: 'var(--red-bg)', borderRadius: 3, border: '1px solid var(--red)' }}>
              <span style={{ fontSize: 9, color: 'var(--red)' }}>NEGATIVE</span><br />{p.negative?.slice(0, 80)}
            </div>
          </div>
          {p.causal_nodes_tested && <div style={{ fontSize: 9, color: 'var(--fg-muted)', marginTop: 3 }}>nodes: {p.causal_nodes_tested.join(', ')}</div>}
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
        <div style={{ display: 'flex', gap: 16, marginBottom: 12 }}>
          <div className="pair-stat"><span className="pair-stat-label">Evaluated</span><span className="pair-stat-value">{d.summary.total_evaluated}</span></div>
          <div className="pair-stat"><span className="pair-stat-label">Eligible</span><span className="pair-stat-value">{d.summary.eligible}</span></div>
          <div className="pair-stat"><span className="pair-stat-label">Pareto</span><span className="pair-stat-value">{d.summary.pareto_size}</span></div>
        </div>
      )}
      <div className="table-wrapper">
        <table className="scorer-table">
          <thead><tr><th>Scorer</th><th>Heldout Acc</th><th>Gap</th><th>Eligible</th><th>Pareto</th></tr></thead>
          <tbody>
            {d.scorer_evaluations?.map((e, i) => (
              <tr key={i}>
                <td>{e.scorer_id}</td>
                <td>{(e.heldout_accuracy * 100).toFixed(0)}%</td>
                <td>{e.heldout_mean_gap?.toFixed(3)}</td>
                <td><span className={`badge-${e.eligible ? 'green' : 'red'}`}>{e.eligible ? '✓' : '✗'}</span></td>
                <td>{e.pareto_member ? <span className="badge-green">★</span> : '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stage7Content({ data }: { data: unknown }) {
  const d = data as { failure_patterns?: Array<{ pattern_id: string; reasoning_error: string; severity: string; scorer_ids?: string[] }>; mutation_instructions?: Array<{ instruction_id: string; instruction: string; targets_failure_patterns: string[] }> };
  return (
    <div>
      <div style={{ fontSize: 10, color: 'var(--fg-muted)', textTransform: 'uppercase', marginBottom: 6 }}>Failure Patterns ({d.failure_patterns?.length})</div>
      {d.failure_patterns?.map((fp, i) => (
        <div key={i} style={{ paddingLeft: 8, borderLeft: `2px solid ${fp.severity === 'high' ? 'var(--red)' : fp.severity === 'medium' ? 'var(--amber)' : 'var(--gray)'}`, marginBottom: 6 }}>
          <div style={{ fontSize: 11 }}><strong>{fp.pattern_id}</strong> <span className={`badge-${fp.severity === 'high' ? 'red' : fp.severity === 'medium' ? 'amber' : 'gray'}`}>{fp.severity}</span></div>
          <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>{fp.reasoning_error}</div>
        </div>
      ))}
      {d.mutation_instructions && d.mutation_instructions.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 10, color: 'var(--green)', textTransform: 'uppercase', marginBottom: 4 }}>Repair Instructions ({d.mutation_instructions.length})</div>
          {d.mutation_instructions.map((mi, i) => (
            <div key={i} style={{ fontSize: 11, marginBottom: 4, color: 'var(--fg)' }}>
              <span style={{ color: 'var(--fg-muted)' }}>{mi.instruction_id}:</span> {mi.instruction}
              <span style={{ fontSize: 9, color: 'var(--fg-muted)' }}> → {mi.targets_failure_patterns?.join(', ')}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Stage8Content({ data }: { data: unknown }) {
  const d = data as { repair_scorers?: Array<{ scorer_id: string; hypothesis: string; functional_form: string; repair_strategy: string; targets_failure_patterns: string[]; code: string }> };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {d.repair_scorers?.map((s, i) => (
        <div key={i} style={{ padding: 10, background: 'var(--bg)', border: '1px solid var(--panel-border)', borderRadius: 4 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 12, fontWeight: 600 }}>{s.scorer_id}</span>
            <span className="badge-green">{s.functional_form}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--fg)', lineHeight: 1.4, marginBottom: 4 }}>{s.hypothesis}</div>
          {s.repair_strategy && <div style={{ fontSize: 10, color: 'var(--amber)' }}>strategy: {s.repair_strategy}</div>}
          {s.targets_failure_patterns && <div style={{ fontSize: 9, color: 'var(--fg-muted)' }}>targets: {s.targets_failure_patterns.join(', ')}</div>}
          {s.code && (
            <details style={{ marginTop: 4 }}>
              <summary style={{ fontSize: 10, color: 'var(--green)', cursor: 'pointer' }}>code</summary>
              <pre style={{ fontSize: 10, color: 'var(--fg-muted)', marginTop: 4, padding: 6, overflow: 'auto', maxHeight: 150, whiteSpace: 'pre-wrap' }}>{s.code}</pre>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}
