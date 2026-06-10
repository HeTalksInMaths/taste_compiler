import Link from "next/link";

export default function DashboardPage() {
  return (
    <div className="px-6 py-16">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12">
          <h1 className="text-3xl font-bold text-white">Platform Dashboard</h1>
          <p className="mt-2" style={{ color: "rgba(255,255,255,0.5)" }}>Stripe integration, payment flow, and marketplace health.</p>
        </div>

        {/* Stripe Integration Status */}
        <div className="glass-card mb-8 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Stripe Integration</h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <StatusItem label="Mode" value="Test (sk_test_*)" status="active" />
            <StatusItem label="Webhooks" value="Listening" status="active" />
            <StatusItem label="Connect" value="Destination charges" status="active" />
            <StatusItem label="Sim Mode" value="mock_only" status="info" />
          </div>
        </div>

        <div className="grid gap-8 lg:grid-cols-2 mb-8">
          <div className="glass-card p-6">
            <h2 className="mb-4 text-lg font-semibold text-white">Revenue Split Model</h2>
            <div className="space-y-4">
              <SplitBar label="Creator payout" percent={70} color="#10b981" />
              <SplitBar label="Platform fee" percent={30} color="#5c7cfa" />
            </div>
            <div className="mt-6 space-y-2 text-sm" style={{ color: "rgba(255,255,255,0.5)" }}>
              {[['Payment processing (SG)', '3.4% + $0.50'], ['Payment processing (US)', '2.9% + $0.30'], ['API cost per reveal', '~$0.35'], ['Custom evaluator build', '~$4.50']].map(([k, v]) => (
                <div key={k} className="flex justify-between"><span>{k}</span><span className="font-mono">{v}</span></div>
              ))}
            </div>
          </div>

          <div className="glass-card p-6">
            <h2 className="mb-4 text-lg font-semibold text-white">Checkout Flow</h2>
            <div className="space-y-3">
              {CHECKOUT_FLOW.map((step, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-mono" style={{ backgroundColor: "rgba(92,124,250,0.1)", color: "rgb(145,167,255)" }}>
                    {i + 1}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-white">{step.action}</div>
                    <div className="text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>{step.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Reveal State Machine */}
        <div className="glass-card mb-8 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Reveal State Machine</h2>
          <div className="flex items-center justify-center gap-2 flex-wrap py-4">
            {STATES.map((state, i) => (
              <div key={state.name} className="flex items-center gap-2">
                <div className="rounded-lg px-3 py-1.5 text-xs font-medium" style={{ border: `1px solid ${state.border}`, backgroundColor: state.bg, color: "rgba(255,255,255,0.8)" }}>
                  {state.name}
                </div>
                {i < STATES.length - 1 && (
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ color: "rgba(255,255,255,0.2)" }}>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                )}
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-lg p-4 text-sm" style={{ backgroundColor: "rgba(255,255,255,0.02)" }}>
            <p className="mb-2" style={{ color: "rgba(255,255,255,0.5)" }}>Key constraints:</p>
            <ul className="list-disc list-inside space-y-1 text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>
              <li>Idempotency key = reveal_id + buyer_id</li>
              <li>Webhook events deduplicated atomically via atomicInsertStripeEvent</li>
              <li>InMemoryAdapter rejected for stripe_test_checkout mode</li>
              <li>Raw body captured via Buffer.from(await request.arrayBuffer())</li>
            </ul>
          </div>
        </div>

        {/* Stripe CLI Setup */}
        <div className="glass-card p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Stripe CLI Setup</h2>
          <p className="text-sm mb-4" style={{ color: "rgba(255,255,255,0.5)" }}>Connect your local dev environment to Stripe test mode for real webhook processing.</p>
          <div className="space-y-3">
            <CodeBlock label="Install Stripe CLI" code="brew install stripe/stripe-cli/stripe" />
            <CodeBlock label="Login" code="stripe login" />
            <CodeBlock label="Forward webhooks to local" code="stripe listen --forward-to localhost:3000/api/stripe/webhook" />
            <CodeBlock label="Set webhook secret in .env.local" code="STRIPE_WEBHOOK_SECRET=whsec_... (from CLI output)" />
            <CodeBlock label="Trigger test events" code="stripe trigger checkout.session.completed" />
          </div>
          <div className="mt-6 rounded-lg p-4" style={{ backgroundColor: "rgba(245,158,11,0.05)", border: "1px solid rgba(245,158,11,0.2)" }}>
            <div className="text-sm font-medium mb-1" style={{ color: "rgb(251,191,36)" }}>Testing with MARKET_SIM_MODE</div>
            <div className="text-xs" style={{ color: "rgba(255,255,255,0.5)" }}>
              Set <code style={{ color: "rgb(251,191,36)" }}>MARKET_SIM_MODE=stripe_test_checkout</code> to create real Stripe checkout sessions during simulation. Requires persistent storage — InMemoryAdapter is rejected.
            </div>
          </div>
        </div>

        {/* Cross-link to Create Scorer */}
        <div className="mt-6 rounded-xl border p-5 flex items-center justify-between" style={{ borderColor: "rgba(177,151,252,0.2)", backgroundColor: "rgba(177,151,252,0.04)" }}>
          <div>
            <div className="text-sm font-medium text-white">Want to add a scorer to the marketplace?</div>
            <div className="text-xs mt-0.5" style={{ color: "rgba(255,255,255,0.4)" }}>Run the full EvalWeaver pipeline and publish your scorer — 70% revenue share.</div>
          </div>
          <Link href="/create" className="text-xs font-medium rounded-lg px-4 py-2 transition" style={{ backgroundColor: "rgba(177,151,252,0.1)", color: "rgb(177,151,252)" }}>
            Create Scorer →
          </Link>
        </div>
      </div>
    </div>
  );
}

function StatusItem({ label, value, status }: { label: string; value: string; status: 'active' | 'info' | 'warn' }) {
  const styles = {
    active: { backgroundColor: 'rgba(16,185,129,0.1)', color: 'rgb(52,211,153)', boxShadow: '0 0 0 1px rgba(16,185,129,0.2)' },
    info: { backgroundColor: 'rgba(92,124,250,0.1)', color: 'rgb(145,167,255)', boxShadow: '0 0 0 1px rgba(92,124,250,0.2)' },
    warn: { backgroundColor: 'rgba(245,158,11,0.1)', color: 'rgb(251,191,36)', boxShadow: '0 0 0 1px rgba(245,158,11,0.2)' },
  };
  return (
    <div>
      <div className="text-xs mb-1" style={{ color: "rgba(255,255,255,0.4)" }}>{label}</div>
      <div className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium" style={styles[status]}>{value}</div>
    </div>
  );
}

function SplitBar({ label, percent, color }: { label: string; percent: number; color: string }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span style={{ color: "rgba(255,255,255,0.6)" }}>{label}</span>
        <span className="font-mono font-semibold text-white">{percent}%</span>
      </div>
      <div className="h-3 rounded-full" style={{ backgroundColor: "rgba(255,255,255,0.06)" }}>
        <div className="h-full rounded-full opacity-70" style={{ width: `${percent}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function CodeBlock({ label, code }: { label: string; code: string }) {
  return (
    <div>
      <div className="text-xs mb-1" style={{ color: "rgba(255,255,255,0.4)" }}>{label}</div>
      <div className="rounded-lg px-4 py-2.5 font-mono text-sm overflow-x-auto" style={{ backgroundColor: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.8)" }}>
        {code}
      </div>
    </div>
  );
}

const CHECKOUT_FLOW = [
  { action: 'Create reveal preview', detail: 'POST /api/reveals/preview → teaser with locked items' },
  { action: 'Start checkout', detail: 'POST /api/stripe/create-reveal-checkout-session → Stripe session' },
  { action: 'Customer pays', detail: 'Stripe Checkout hosted page → payment intent captured' },
  { action: 'Webhook received', detail: 'checkout.session.completed → atomic state transition' },
  { action: 'Reveal unlocked', detail: 'Full report accessible via GET /api/reveals/:id' },
];

const STATES = [
  { name: 'preview', bg: 'rgba(255,255,255,0.02)', border: 'rgba(255,255,255,0.2)' },
  { name: 'checkout_created', bg: 'rgba(92,124,250,0.05)', border: 'rgba(92,124,250,0.3)' },
  { name: 'paid', bg: 'rgba(16,185,129,0.05)', border: 'rgba(16,185,129,0.3)' },
  { name: 'revealed', bg: 'rgba(124,58,237,0.05)', border: 'rgba(124,58,237,0.3)' },
  { name: 'refunded', bg: 'rgba(248,113,113,0.05)', border: 'rgba(248,113,113,0.3)' },
];
