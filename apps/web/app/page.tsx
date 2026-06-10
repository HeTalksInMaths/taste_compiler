import Link from "next/link";

export default function Home() {
  return (
    <main className="px-6 py-20">
      <div className="mx-auto max-w-3xl text-center">
        <h1 className="text-4xl font-bold text-white tracking-tight leading-tight">
          Turn subjective taste into executable scorers.
        </h1>
        <p className="mt-4 text-lg leading-relaxed" style={{ color: "rgba(255,255,255,0.55)" }}>
          Give Taste Compiler a quality target and reference text. It researches what that quality means,
          generates scorer logic, validates score lift, and market-tests whether people would pay to reveal the result.
        </p>

        <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <Link
            href="/create"
            className="rounded-lg px-8 py-3.5 text-sm font-medium text-white transition"
            style={{ background: "linear-gradient(to right, #4c6ef5, #7c3aed)" }}
          >
            Create a Scorer
          </Link>
          <Link
            href="/runs/demo"
            className="rounded-lg px-8 py-3.5 text-sm font-medium transition"
            style={{ border: "1px solid rgba(255,255,255,0.15)", color: "rgba(255,255,255,0.7)" }}
          >
            View Demo Run
          </Link>
        </div>

        <div className="mt-6">
          <Link
            href="/stages"
            className="text-xs transition"
            style={{ color: "rgba(255,255,255,0.35)" }}
          >
            Run the live pipeline yourself →
          </Link>
        </div>

        {/* How it works */}
        <div className="mt-20 grid gap-6 sm:grid-cols-3 text-left">
          <div className="rounded-xl p-5" style={{ border: "1px solid rgba(255,255,255,0.06)", backgroundColor: "rgba(255,255,255,0.02)" }}>
            <div className="text-sm font-semibold text-white mb-2">1. Define quality</div>
            <p className="text-xs leading-relaxed" style={{ color: "rgba(255,255,255,0.45)" }}>
              Choose a quality target like &ldquo;trustworthy&rdquo; or &ldquo;persuasive&rdquo; and paste reference text.
              The system researches what that quality actually means in language.
            </p>
          </div>
          <div className="rounded-xl p-5" style={{ border: "1px solid rgba(255,255,255,0.06)", backgroundColor: "rgba(255,255,255,0.02)" }}>
            <div className="text-sm font-semibold text-white mb-2">2. Generate and test</div>
            <p className="text-xs leading-relaxed" style={{ color: "rgba(255,255,255,0.45)" }}>
              Taste Compiler generates scorer hypotheses, tests them on positive/negative pairs,
              identifies failures, and repairs the scorer logic automatically.
            </p>
          </div>
          <div className="rounded-xl p-5" style={{ border: "1px solid rgba(255,255,255,0.06)", backgroundColor: "rgba(255,255,255,0.02)" }}>
            <div className="text-sm font-semibold text-white mb-2">3. Market-test and sell</div>
            <p className="text-xs leading-relaxed" style={{ color: "rgba(255,255,255,0.45)" }}>
              Simulate demand with Nemotron personas, estimate conversion, and gate the full result
              behind a Stripe reveal for real monetization.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
