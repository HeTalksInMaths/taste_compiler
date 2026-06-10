const EXPERIMENTS = [
  {
    goal: 'concise',
    raw_text: 'EvalWeaver helps writers identify and eliminate unnecessary words...',
    scorers_r0: 8,
    scorers_r1: 6,
    pareto_r0: 5,
    pareto_r1: 7,
    ensemble_size: 7,
    best_accuracy: 0.8,
    best_margin: 0.292,
    selected_candidate: 'C001',
    ensemble_score: 0.9453,
    criteria_pass: 19,
    criteria_warn: 1,
    criteria_fail: 0,
  },
  {
    goal: 'persuasive',
    raw_text: 'EvalWeaver lets anyone create, use, and monetize AI improvers...',
    scorers_r0: 8,
    scorers_r1: 6,
    pareto_r0: 4,
    pareto_r1: 6,
    ensemble_size: 6,
    best_accuracy: 0.75,
    best_margin: 0.256,
    selected_candidate: 'C001',
    ensemble_score: 0.891,
    criteria_pass: 18,
    criteria_warn: 2,
    criteria_fail: 0,
  },
];

export default function ExperimentsPage() {
  return (
    <div className="px-6 py-16">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12">
          <h1 className="text-3xl font-bold">Pipeline Experiments</h1>
          <p className="mt-2 text-white/50">
            Results from automated scorer discovery and evolution runs.
          </p>
        </div>

        <div className="space-y-8">
          {EXPERIMENTS.map((exp) => (
            <ExperimentCard key={exp.goal} experiment={exp} />
          ))}
        </div>
      </div>
    </div>
  );
}

function ExperimentCard({ experiment: exp }: { experiment: (typeof EXPERIMENTS)[number] }) {
  return (
    <div className="glass-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.06] px-6 py-4">
        <div className="flex items-center gap-4">
          <span className="rounded-lg bg-brand-500/10 px-3 py-1.5 text-sm font-semibold text-brand-400 capitalize">
            {exp.goal}
          </span>
          <span className="text-sm text-white/40 max-w-md truncate">{exp.raw_text}</span>
        </div>
        <CriteriaIndicator pass={exp.criteria_pass} warn={exp.criteria_warn} fail={exp.criteria_fail} />
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-px bg-white/[0.04] sm:grid-cols-4 lg:grid-cols-6">
        <MetricCell label="Scorers R0" value={exp.scorers_r0} />
        <MetricCell label="Scorers R1" value={exp.scorers_r1} />
        <MetricCell label="Pareto R0" value={exp.pareto_r0} />
        <MetricCell label="Pareto R1" value={exp.pareto_r1} />
        <MetricCell label="Ensemble" value={exp.ensemble_size} />
        <MetricCell label="Best Acc" value={`${(exp.best_accuracy * 100).toFixed(0)}%`} highlight />
      </div>

      {/* Results */}
      <div className="flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-6">
          <div>
            <div className="text-xs text-white/40">Selected Candidate</div>
            <div className="font-mono text-sm font-semibold text-brand-400">{exp.selected_candidate}</div>
          </div>
          <div>
            <div className="text-xs text-white/40">Ensemble Score</div>
            <div className="text-sm font-semibold text-emerald-400">{exp.ensemble_score.toFixed(4)}</div>
          </div>
          <div>
            <div className="text-xs text-white/40">Best Margin</div>
            <div className="text-sm font-semibold text-white/80">{exp.best_margin.toFixed(3)}</div>
          </div>
        </div>
        <button className="rounded-lg border border-white/10 px-4 py-2 text-sm text-white/60 transition hover:bg-white/5">
          View Details →
        </button>
      </div>
    </div>
  );
}

function MetricCell({ label, value, highlight }: { label: string; value: string | number; highlight?: boolean }) {
  return (
    <div className="bg-[hsl(var(--background))] px-4 py-4 text-center">
      <div className={`text-lg font-semibold ${highlight ? 'text-emerald-400' : 'text-white/90'}`}>{value}</div>
      <div className="mt-0.5 text-xs text-white/40">{label}</div>
    </div>
  );
}

function CriteriaIndicator({ pass, warn, fail }: { pass: number; warn: number; fail: number }) {
  const total = pass + warn + fail;
  return (
    <div className="flex items-center gap-2">
      <div className="flex h-2 w-24 overflow-hidden rounded-full bg-white/10">
        <div className="bg-emerald-500" style={{ width: `${(pass / total) * 100}%` }} />
        <div className="bg-amber-500" style={{ width: `${(warn / total) * 100}%` }} />
        <div className="bg-red-500" style={{ width: `${(fail / total) * 100}%` }} />
      </div>
      <span className="text-xs text-white/40">{pass}/{total}</span>
    </div>
  );
}
