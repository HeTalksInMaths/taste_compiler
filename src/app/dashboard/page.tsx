export default function DashboardPage() {
  return (
    <div className="px-6 py-16">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12">
          <h1 className="text-3xl font-bold">Platform Dashboard</h1>
          <p className="mt-2 text-white/50">Stripe integration, payment flow, and marketplace health.</p>
        </div>

        {/* Stripe Integration Status */}
        <div className="glass-card mb-8 p-6">
          <h2 className="mb-4 text-lg font-semibold">Stripe Integration</h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <StatusItem label="Mode" value="Test (sk_test_*)" status="active" />
            <StatusItem label="Webhooks" value="Listening" status="active" />
            <StatusItem label="Connect" value="Destination charges" status="active" />
            <StatusItem label="Sim Mode" value="mock_only" status="info" />
          </div>
        </div>

        {/* Revenue Split Visualization */}
        <div className="grid gap-8 lg:grid-cols-2 mb-8">
          <div className="glass-card p-6">
            <h2 className="mb-4 text-lg font-semibold">Revenue Split Model</h2>
            <div className="space-y-4">
              <SplitBar label="Creator payout" percent={70} color="bg-emerald-500" />
              <SplitBar label="Platform fee" percent={30} color="bg-brand-500" />
            </div>
            <div className="mt-6 space-y-2 text-sm text-white/50">
              <div className="flex justify-between">
                <span>Payment processing (SG)</span>
                <span className="font-mono">3.4% + $0.50</span>
              </div>
              <div className="flex justify-between">
                <span>Payment processing (US)</span>
                <span className="font-mono">2.9% + $0.30</span>
              </div>
              <div className="flex justify-between">
                <span>API cost per reveal</span>
                <span className="font-mono">~$0.35</span>
              </div>
              <div className="flex justify-between">
                <span>Custom evaluator build</span>
                <span className="font-mono">~$4.50</span>
              </div>
            </div>
          </div>

          <div className="glass-card p-6">
            <h2 className="mb-4 text-lg font-semibold">Checkout Flow</h2>
            <div className="space-y-3">
              {CHECKOUT_FLOW.map((step, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-500/10 text-xs font-mono text-brand-400">
                    {i + 1}
                  </div>
                  <div>
                    <div className="text-sm font-medium">{step.action}</div>
                    <div className="text-xs text-white/40">{step.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Reveal State Machine */}
        <div className="glass-card mb-8 p-6">
          <h2 className="mb-4 text-lg font-semibold">Reveal State Machine</h2>
          <div className="flex items-center justify-center gap-2 flex-wrap py-4">
            {STATES.map((state, i) => (
              <div key={state.name} className="flex items-center gap-2">
                <div className={`rounded-lg px-3 py-1.5 text-xs font-medium border ${state.border} ${state.bg}`}>
                  {state.name}
                </div>
                {i < STATES.length - 1 && (
                  <svg className="h-4 w-4 text-white/20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                )}
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-lg bg-white/[0.02] p-4 text-sm text-white/50">
            <p className="mb-2">Key constraints:</p>
            <ul className="list-disc list-inside space-y-1 text-xs text-white/40">
              <li>Idempotency key = reveal_id + buyer_id</li>
              <li>Webhook events deduplicated atomically via atomicInsertStripeEvent</li>
              <li>InMemoryAdapter rejected for stripe_test_checkout mode</li>
              <li>Raw body captured via Buffer.from(await request.arrayBuffer())</li>
            </ul>
          </div>
        </div>

        {/* Stripe CLI Setup */}
        <div className="glass-card p-6">
          <h2 className="mb-4 text-lg font-semibold">Stripe CLI Setup</h2>
          <p className="text-sm text-white/50 mb-4">
            Connect your local dev environment to Stripe test mode for real webhook processing.
          </p>
          <div className="space-y-3">
            <CodeBlock label="Install Stripe CLI" code="brew install stripe/stripe-cli/stripe" />
            <CodeBlock label="Login" code="stripe login" />
            <CodeBlock label="Forward webhooks to local" code="stripe listen --forward-to localhost:3000/api/stripe/webhook" />
            <CodeBlock label="Set webhook secret in .env.local" code="STRIPE_WEBHOOK_SECRET=whsec_... (from CLI output)" />
            <CodeBlock label="Trigger test events" code="stripe trigger checkout.session.completed" />
          </div>
          <div className="mt-6 rounded-lg bg-amber-500/5 border border-amber-500/20 p-4">
            <div className="text-sm font-medium text-amber-400 mb-1">Testing with MARKET_SIM_MODE</div>
            <div className="text-xs text-white/50">
              Set <code className="text-amber-300">MARKET_SIM_MODE=stripe_test_checkout</code> to create real Stripe checkout sessions
              during simulation (capped at <code className="text-amber-300">STRIPE_TEST_SESSION_CAP=50</code>).
              Requires persistent storage (postgres or dynamodb) — InMemoryAdapter is rejected.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusItem({ label, value, status }: { label: string; value: string; status: 'active' | 'info' | 'warn' }) {
  const colors = {
    active: 'bg-emerald-500/10 text-emerald-400 ring-emerald-500/20',
    info: 'bg-brand-500/10 text-brand-300 ring-brand-500/20',
    warn: 'bg-amber-500/10 text-amber-400 ring-amber-500/20',
  };
  return (
    <div>
      <div className="text-xs text-white/40 mb-1">{label}</div>
      <div className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${colors[status]}`}>
        {value}
      </div>
    </div>
  );
}

function SplitBar({ label, percent, color }: { label: string; percent: number; color: string }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-white/60">{label}</span>
        <span className="font-mono font-semibold">{percent}%</span>
      </div>
      <div className="h-3 rounded-full bg-white/[0.06]">
        <div className={`h-full rounded-full ${color} opacity-70`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function CodeBlock({ label, code }: { label: string; code: string }) {
  return (
    <div>
      <div className="text-xs text-white/40 mb-1">{label}</div>
      <div className="rounded-lg bg-black/40 border border-white/[0.06] px-4 py-2.5 font-mono text-sm text-white/80 overflow-x-auto">
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
  { name: 'preview', bg: 'bg-white/5', border: 'border-white/20' },
  { name: 'checkout_created', bg: 'bg-brand-500/5', border: 'border-brand-500/30' },
  { name: 'paid', bg: 'bg-emerald-500/5', border: 'border-emerald-500/30' },
  { name: 'revealed', bg: 'bg-purple-500/5', border: 'border-purple-500/30' },
  { name: 'refunded', bg: 'bg-red-500/5', border: 'border-red-500/30' },
];
