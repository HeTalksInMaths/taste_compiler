'use client';

import { useState } from 'react';

type StageStatus = 'idle' | 'running' | 'done' | 'error';

interface StageState {
  status: StageStatus;
  data: unknown;
  error?: string;
}

const STAGE_LABELS = [
  'Causal Research',
  'Causal Graph',
  'Measurement Research',
  'Scorer Hypotheses',
];

const VARIABLES = ['trustworthy', 'persuasive', 'concise', 'urgent', 'funny', 'professional', 'empathetic', 'data-driven'];

export default function StagesPage() {
  const [targetVariable, setTargetVariable] = useState('trustworthy');
  const [stages, setStages] = useState<StageState[]>([
    { status: 'idle', data: null },
    { status: 'idle', data: null },
    { status: 'idle', data: null },
    { status: 'idle', data: null },
  ]);
  const [currentStage, setCurrentStage] = useState(0);
  const [running, setRunning] = useState(false);

  async function runStage(stageNum: number, previousOutput: unknown) {
    setStages(prev => prev.map((s, i) => i === stageNum ? { status: 'running', data: null } : s));
    try {
      const res = await fetch('/api/stages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_variable: targetVariable,
          stage: stageNum + 1,
          previous_output: previousOutput,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      const { result } = await res.json();
      setStages(prev => prev.map((s, i) => i === stageNum ? { status: 'done', data: result } : s));
      return result;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error';
      setStages(prev => prev.map((s, i) => i === stageNum ? { status: 'error', data: null, error: msg } : s));
      return null;
    }
  }

  async function runAll() {
    setRunning(true);
    setStages([
      { status: 'idle', data: null },
      { status: 'idle', data: null },
      { status: 'idle', data: null },
      { status: 'idle', data: null },
    ]);

    let prevOutput: unknown = null;

    for (let i = 0; i < 4; i++) {
      setCurrentStage(i);
      const result = await runStage(i, prevOutput);
      if (!result) break;
      prevOutput = result;
    }
    setRunning(false);
  }

  return (
    <main className="run-page">
      <div className="run-header">
        <h1 className="run-id">Stages 1–4 Live Pipeline</h1>
        <p className="run-raw-text">
          Causal Research → Causal Graph → Measurement Research → Scorer Hypotheses
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
                onClick={() => setTargetVariable(v)}
                className={`btn ${targetVariable === v ? 'btn-primary' : ''}`}
                style={{ padding: '6px 14px', fontSize: 12 }}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={runAll}
          disabled={running}
          className="btn btn-primary"
          style={{ opacity: running ? 0.5 : 1 }}
        >
          {running ? `Running Stage ${currentStage + 1}/4...` : 'Run All 4 Stages →'}
        </button>
      </div>

      {/* Pipeline Progress */}
      <div className="panel">
        <div className="panel-header">Pipeline Progress</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {STAGE_LABELS.map((label, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span className={`badge-${getBadgeColor(stages[i].status)}`}>
                {stages[i].status === 'running' ? '⟳' : stages[i].status === 'done' ? '✓' : stages[i].status === 'error' ? '✗' : '○'} {label}
              </span>
              {i < 3 && <span style={{ color: 'var(--fg-muted)' }}>→</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Stage Outputs */}
      {stages[0].status !== 'idle' && (
        <Stage1Panel data={stages[0]} />
      )}
      {stages[1].status !== 'idle' && (
        <Stage2Panel data={stages[1]} />
      )}
      {stages[2].status !== 'idle' && (
        <Stage3Panel data={stages[2]} />
      )}
      {stages[3].status !== 'idle' && (
        <Stage4Panel data={stages[3]} />
      )}
    </main>
  );
}

function getBadgeColor(status: StageStatus): string {
  if (status === 'done') return 'green';
  if (status === 'running') return 'amber';
  if (status === 'error') return 'red';
  return 'gray';
}

function Stage1Panel({ data }: { data: StageState }) {
  if (data.status === 'running') return <LoadingPanel title="Stage 1 — Causal Research" />;
  if (data.status === 'error') return <ErrorPanel title="Stage 1" error={data.error!} />;
  if (!data.data) return null;
  const d = data.data as { causal_research?: Array<{ claim: string; causal_variable: string; effect_direction: string; mechanism: string }>; research_tensions?: Array<{ claim: string }> };
  return (
    <div className="panel">
      <div className="panel-header">Stage 1 — Causal Research ({d.causal_research?.length ?? 0} items)</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {d.causal_research?.slice(0, 8).map((item, i) => (
          <div key={i} style={{ paddingLeft: 8, borderLeft: `2px solid ${item.effect_direction === 'increases' ? 'var(--green)' : item.effect_direction === 'decreases' ? 'var(--red)' : 'var(--amber)'}` }}>
            <div style={{ fontSize: 13 }}><strong>{item.causal_variable}</strong> <span className={`badge-${item.effect_direction === 'increases' ? 'green' : item.effect_direction === 'decreases' ? 'red' : 'amber'}`}>{item.effect_direction}</span></div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>{item.claim}</div>
            {item.mechanism && <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 2, fontStyle: 'italic' }}>↳ {item.mechanism}</div>}
          </div>
        ))}
      </div>
      {d.research_tensions && d.research_tensions.length > 0 && (
        <div style={{ marginTop: 12, paddingTop: 8, borderTop: '1px solid var(--panel-border)' }}>
          <div style={{ fontSize: 11, color: 'var(--amber)', textTransform: 'uppercase', marginBottom: 4 }}>Tensions</div>
          {d.research_tensions.map((t, i) => (
            <div key={i} style={{ fontSize: 12, color: 'var(--fg-muted)' }}>⚡ {t.claim}</div>
          ))}
        </div>
      )}
    </div>
  );
}

function Stage2Panel({ data }: { data: StageState }) {
  if (data.status === 'running') return <LoadingPanel title="Stage 2 — Causal Graph" />;
  if (data.status === 'error') return <ErrorPanel title="Stage 2" error={data.error!} />;
  if (!data.data) return null;
  const d = data.data as { causal_nodes?: Array<{ node_id: string; label: string; role: string; mechanism: string }>; causal_edges?: Array<{ from: string; to: string; relationship: string }>; summary_theory?: string };
  return (
    <div className="panel">
      <div className="panel-header">Stage 2 — Causal Graph ({d.causal_nodes?.length ?? 0} nodes, {d.causal_edges?.length ?? 0} edges)</div>
      {d.summary_theory && <div style={{ fontSize: 13, color: 'var(--fg)', marginBottom: 12, lineHeight: 1.5 }}>{d.summary_theory}</div>}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', marginBottom: 6 }}>Nodes</div>
          {d.causal_nodes?.map((n, i) => (
            <div key={i} style={{ marginBottom: 6, paddingLeft: 8, borderLeft: '2px solid var(--panel-border)' }}>
              <div style={{ fontSize: 12 }}><strong>{n.label}</strong> <span className={`badge-${n.role === 'increases' ? 'green' : n.role === 'decreases' ? 'red' : 'amber'}`}>{n.role}</span></div>
              <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>{n.mechanism?.slice(0, 80)}</div>
            </div>
          ))}
        </div>
        <div>
          <div style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', marginBottom: 6 }}>Edges</div>
          {d.causal_edges?.map((e, i) => (
            <div key={i} style={{ fontSize: 12, marginBottom: 4 }}>
              <span style={{ color: 'var(--green)' }}>{e.from}</span>
              <span style={{ color: 'var(--fg-muted)' }}> → </span>
              <span style={{ color: 'var(--green)' }}>{e.to}</span>
              <span style={{ color: 'var(--fg-muted)', fontSize: 11 }}> ({e.relationship})</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stage3Panel({ data }: { data: StageState }) {
  if (data.status === 'running') return <LoadingPanel title="Stage 3 — Measurement Research" />;
  if (data.status === 'error') return <ErrorPanel title="Stage 3" error={data.error!} />;
  if (!data.data) return null;
  const d = data.data as { measurement_research?: Array<{ causal_node: string; measurement_claim: string; text_features: string[]; implementation_ideas: string[] }> };
  return (
    <div className="panel">
      <div className="panel-header">Stage 3 — Measurement Research ({d.measurement_research?.length ?? 0} items)</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {d.measurement_research?.map((m, i) => (
          <div key={i} style={{ paddingLeft: 8, borderLeft: '2px solid var(--amber)' }}>
            <div style={{ fontSize: 12 }}><strong>{m.causal_node}</strong></div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{m.measurement_claim}</div>
            <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 2 }}>
              features: {m.text_features?.join(', ')}
            </div>
            <div style={{ fontSize: 11, color: 'var(--green)', marginTop: 2 }}>
              → {m.implementation_ideas?.slice(0, 3).join(' | ')}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Stage4Panel({ data }: { data: StageState }) {
  if (data.status === 'running') return <LoadingPanel title="Stage 4 — Scorer Hypotheses" />;
  if (data.status === 'error') return <ErrorPanel title="Stage 4" error={data.error!} />;
  if (!data.data) return null;
  const d = data.data as { scorers?: Array<{ scorer_id: string; hypothesis: string; functional_form: string; causal_nodes_used: string[]; code: string }> };
  return (
    <div className="panel">
      <div className="panel-header">Stage 4 — Scorer Hypotheses ({d.scorers?.length ?? 0} scorers)</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {d.scorers?.map((s, i) => (
          <div key={i} style={{ padding: 12, background: 'var(--bg)', border: '1px solid var(--panel-border)', borderRadius: 4 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>{s.scorer_id}</span>
              <span className="badge-amber">{s.functional_form}</span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--fg)', marginBottom: 6, lineHeight: 1.4 }}>{s.hypothesis}</div>
            {s.causal_nodes_used && (
              <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginBottom: 6 }}>
                nodes: {s.causal_nodes_used.join(', ')}
              </div>
            )}
            {s.code && (
              <details>
                <summary style={{ fontSize: 11, color: 'var(--green)', cursor: 'pointer' }}>View code</summary>
                <pre style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 4, padding: 8, background: 'var(--bg)', borderRadius: 4, overflow: 'auto', maxHeight: 200, whiteSpace: 'pre-wrap' }}>{s.code}</pre>
              </details>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function LoadingPanel({ title }: { title: string }) {
  return (
    <div className="panel">
      <div className="panel-header">{title}</div>
      <div style={{ fontSize: 13, color: 'var(--amber)' }}>⟳ Calling Bedrock Claude Sonnet 4.6...</div>
    </div>
  );
}

function ErrorPanel({ title, error }: { title: string; error: string }) {
  return (
    <div className="panel error-panel">
      <div className="panel-header">{title} — Error</div>
      <div style={{ fontSize: 13, color: 'var(--red)' }}>{error}</div>
    </div>
  );
}
