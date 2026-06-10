import demoData from '@/fixtures/demo_run_persuasive.json';
import Link from 'next/link';

type Scorer = { scorer_id: string; hypothesis: string; functional_form: string; text_features_used?: string[]; code?: string };
type Evaluation = { scorer_id: string; heldout_accuracy: number; heldout_mean_gap: number; eligible: boolean; pareto_member: boolean };
type RepairEval = { scorer_id: string; accuracy: number; mean_gap: number };
type RepairScorer = { scorer_id: string; hypothesis: string; repair_strategy: string; text_features_used?: string[]; code?: string };

const stages = demoData.stages as Record<string, unknown>;
const s4 = stages.stage4 as { scorers: Scorer[] };
const s6 = stages.stage6 as { scorer_evaluations: Evaluation[]; pareto_frontier: string[]; summary: { total_evaluated: number; eligible: number; pareto_size: number } };
const s8 = stages.stage8 as { repair_scorers: RepairScorer[]; repair_evaluations: RepairEval[]; comparison: { best_original: { scorer_id: string; accuracy: number; gap: number } | null; best_repair: { scorer_id: string; accuracy: number; gap: number } | null; improvement: number | null } };

export default function DemoRunPage() {
  const bestScorer = s6.scorer_evaluations.reduce((best, e) => e.heldout_mean_gap > best.heldout_mean_gap ? e : best, s6.scorer_evaluations[0]);
  const bestScorerDetail = s4.scorers.find(s => s.scorer_id === bestScorer.scorer_id);

  return (
    <div className="px-6 py-12">
      <div className="mx-auto max-w-4xl">
        {/* Header */}
        <div className="mb-8">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs" style={{ backgroundColor: 'rgba(16,185,129,0.1)', color: 'rgb(52,211,153)', border: '1px solid rgba(16,185,129,0.2)' }}>
            ✓ Completed Run
          </div>
          <h1 className="text-2xl font-bold text-white">Demo Run: &ldquo;persuasive&rdquo;</h1>
          <p className="mt-2 text-sm" style={{ color: 'rgba(255,255,255,0.5)' }}>
            Quality target: make text more persuasive. 8 stages completed with real Bedrock + Exa search. Repair scorer R1 improved separation by +0.5 gap over the best original.
          </p>
        </div>

        {/* Key Result */}
        <div className="glass-card p-6 mb-6">
          <h2 className="text-lg font-semibold text-white mb-4">Best Scorer Discovered</h2>
          <div className="rounded-lg p-5 mb-4" style={{ backgroundColor: 'rgba(76,110,245,0.06)', border: '1px solid rgba(76,110,245,0.2)' }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-white">{bestScorerDetail?.scorer_id}</span>
              <span className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(16,185,129,0.15)', color: 'rgb(52,211,153)' }}>
                {(bestScorer.heldout_accuracy * 100).toFixed(0)}% accuracy · {bestScorer.heldout_mean_gap.toFixed(1)} gap
              </span>
            </div>
            <p className="text-sm mb-3" style={{ color: 'rgba(255,255,255,0.7)' }}>{bestScorerDetail?.hypothesis}</p>
            {bestScorerDetail?.text_features_used && (
              <div className="flex flex-wrap gap-1.5 mb-3">
                {bestScorerDetail.text_features_used.map((f, i) => (
                  <span key={i} className="rounded-full px-2.5 py-0.5 text-[10px]" style={{ backgroundColor: 'rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.5)', border: '1px solid rgba(255,255,255,0.08)' }}>{f}</span>
                ))}
              </div>
            )}
            {bestScorerDetail?.code && (
              <details>
                <summary className="text-xs cursor-pointer" style={{ color: 'rgb(76,110,245)' }}>View scorer code</summary>
                <pre className="mt-2 p-3 rounded text-[11px] overflow-auto max-h-48" style={{ backgroundColor: 'rgba(0,0,0,0.4)', color: 'rgba(255,255,255,0.5)', whiteSpace: 'pre-wrap' }}>{bestScorerDetail.code}</pre>
              </details>
            )}
          </div>
        </div>

        {/* Evaluation Scoreboard */}
        <div className="glass-card p-6 mb-6">
          <h2 className="text-lg font-semibold text-white mb-4">Scorer Evaluation</h2>
          <div className="flex gap-6 mb-4">
            <div className="text-center"><div className="text-xl font-bold text-white">{s6.summary.total_evaluated}</div><div className="text-[10px]" style={{ color: 'rgba(255,255,255,0.4)' }}>Evaluated</div></div>
            <div className="text-center"><div className="text-xl font-bold" style={{ color: 'rgb(52,211,153)' }}>{s6.summary.eligible}</div><div className="text-[10px]" style={{ color: 'rgba(255,255,255,0.4)' }}>Eligible</div></div>
            <div className="text-center"><div className="text-xl font-bold" style={{ color: 'rgb(76,110,245)' }}>{s6.summary.pareto_size}</div><div className="text-[10px]" style={{ color: 'rgba(255,255,255,0.4)' }}>Pareto</div></div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr style={{ color: 'rgba(255,255,255,0.4)' }}><th className="text-left py-1.5">Scorer</th><th className="text-left">Accuracy</th><th className="text-left">Gap</th><th className="text-left">Eligible</th><th className="text-left">Pareto</th></tr></thead>
              <tbody>
                {s6.scorer_evaluations.map((e, i) => (
                  <tr key={i} style={{ color: 'rgba(255,255,255,0.6)' }}>
                    <td className="py-1.5 font-medium text-white">{e.scorer_id}</td>
                    <td>{(e.heldout_accuracy * 100).toFixed(0)}%</td>
                    <td>{e.heldout_mean_gap.toFixed(2)}</td>
                    <td>{e.eligible ? <span style={{ color: 'rgb(52,211,153)' }}>✓</span> : <span style={{ color: 'rgb(248,113,113)' }}>✗</span>}</td>
                    <td>{e.pareto_member ? <span style={{ color: 'rgb(76,110,245)' }}>★</span> : '–'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Repair Comparison */}
        {s8.comparison && (
          <div className="glass-card p-6 mb-6">
            <h2 className="text-lg font-semibold text-white mb-4">Repair vs Original</h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-lg p-4" style={{ backgroundColor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
                <div className="text-[10px] uppercase mb-2" style={{ color: 'rgba(255,255,255,0.3)', letterSpacing: '0.05em' }}>Best Original</div>
                <div className="text-sm font-medium text-white">{s8.comparison.best_original?.scorer_id}</div>
                <div className="text-xs mt-1" style={{ color: 'rgba(255,255,255,0.5)' }}>
                  Accuracy: {((s8.comparison.best_original?.accuracy || 0) * 100).toFixed(0)}% · Gap: {s8.comparison.best_original?.gap?.toFixed(2)}
                </div>
              </div>
              <div className="rounded-lg p-4" style={{ backgroundColor: 'rgba(76,110,245,0.04)', border: '1px solid rgba(76,110,245,0.15)' }}>
                <div className="text-[10px] uppercase mb-2" style={{ color: 'rgba(76,110,245,0.7)', letterSpacing: '0.05em' }}>Best Repair</div>
                <div className="text-sm font-medium text-white">{s8.comparison.best_repair?.scorer_id}</div>
                <div className="text-xs mt-1" style={{ color: 'rgba(255,255,255,0.5)' }}>
                  Accuracy: {((s8.comparison.best_repair?.accuracy || 0) * 100).toFixed(0)}% · Gap: {s8.comparison.best_repair?.gap?.toFixed(2)}
                </div>
              </div>
            </div>
            {s8.comparison.improvement !== null && (
              <div className="mt-3 text-xs text-center" style={{ color: s8.comparison.improvement > 0 ? 'rgb(52,211,153)' : 'rgba(255,255,255,0.4)' }}>
                {s8.comparison.improvement > 0 ? `+${s8.comparison.improvement} gap improvement` : 'Original scorers already strong — repair matched but did not exceed'}
              </div>
            )}
          </div>
        )}

        {/* All Scorers */}
        <details className="glass-card p-6 mb-6">
          <summary className="text-lg font-semibold text-white cursor-pointer">All Scorer Hypotheses ({s4.scorers.length})</summary>
          <div className="mt-4 space-y-3">
            {s4.scorers.map((s, i) => (
              <div key={i} className="rounded-lg p-4" style={{ backgroundColor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
                <div className="flex justify-between items-center mb-1">
                  <span className="text-xs font-semibold text-white">{s.scorer_id}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(251,191,36,0.1)', color: 'rgb(251,191,36)' }}>{s.functional_form}</span>
                </div>
                <div className="text-[11px] mb-2" style={{ color: 'rgba(255,255,255,0.5)' }}>{s.hypothesis}</div>
                {s.text_features_used && <div className="text-[10px]" style={{ color: 'rgba(255,255,255,0.3)' }}>Features: {s.text_features_used.join(', ')}</div>}
              </div>
            ))}
          </div>
        </details>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row gap-3 mt-8">
          <Link href="/create" className="flex-1 rounded-lg px-5 py-3 text-center text-sm font-medium transition" style={{ background: 'linear-gradient(to right, #4c6ef5, #7c3aed)', color: 'white' }}>
            Create your own scorer →
          </Link>
          <Link href="/stages" className="flex-1 rounded-lg px-5 py-3 text-center text-sm font-medium transition" style={{ border: '1px solid rgba(255,255,255,0.15)', color: 'rgba(255,255,255,0.7)' }}>
            Run the pipeline live →
          </Link>
        </div>
      </div>
    </div>
  );
}
