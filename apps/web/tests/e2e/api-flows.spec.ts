import { test, expect } from '@playwright/test';

// Mocked API responses — tests don't hit real AWS/Stripe/Exa
const STAGES_MOCK = {
  stage: 1, target_variable: 'trustworthy', search_results: [],
  model: 'us.anthropic.claude-sonnet-4-6',
  result: {
    target_variable: 'trustworthy',
    causal_research: [
      { source_id: 'SRC_001', claim: 'Consistent messaging increases perceived trustworthiness.', causal_variable: 'consistency', effect_direction: 'increases', mechanism: 'Predictable behavior reduces uncertainty.', evidence_strength: 'high' },
    ],
    research_tensions: [{ claim: 'Formal tone vs. approachable warmth', variables: ['formality', 'warmth'] }],
  },
};

const DEMAND_MOCK = {
  step: 'demand',
  result: {
    segment_demand: [
      { segment: 'startup_founder_operator', label: 'Startup Founder', base_intent: 0.72, reveal_probability: 0.45, estimated_buyers_per_100: 45 },
      { segment: 'marketing_growth_lead', label: 'Marketing / Growth', base_intent: 0.78, reveal_probability: 0.50, estimated_buyers_per_100: 50 },
    ],
    avg_conversion_rate: 0.47,
    estimated_revenue_per_100_personas: 235,
    estimated_platform_take: 49,
  },
};

const LIVE_SIM_MOCK = {
  simulation: 'nemotron_persona_v2_1_live',
  personas_total: 5, buyers: 3, bounced: 2,
  conversion_rate: 0.6, total_revenue_cents: 1697,
  platform_take_cents: 356, stripe_sessions_created: 2,
  results: [
    { persona_id: 'SG_003', segment: 'startup_founder_operator', job_role: 'startup founder', market: 'Singapore', content_job: 'launch post', selected_scorer: 'Persuasive Without Hype', scorer_id: 'persuasive_without_hype', fit_score: 0.75, reveal_probability: 0.64, will_buy: true, stripe_session_id: 'cs_test_abc123', stripe_session_url: 'https://checkout.stripe.com/pay/cs_test_abc123' },
    { persona_id: 'US_042', segment: 'skeptical_control', job_role: 'finance analyst', market: 'United States', content_job: 'internal memo', selected_scorer: 'Scientific But Readable', scorer_id: 'scientific_but_readable', fit_score: 0.25, reveal_probability: 0.12, will_buy: false, stripe_session_id: null, stripe_session_url: null },
  ],
};

// Next.js 14 App Router fires `networkidle` before React finishes hydrating.
// Without this wait, clicks land before React attaches handlers and are dropped.
async function waitForReactHydration(page: import('@playwright/test').Page) {
  await page.waitForFunction(() => {
    const el = document.querySelector('button');
    if (!el) return false;
    return Object.getOwnPropertyNames(el).some(
      k => k.startsWith('__reactFiber') || k.startsWith('__reactProps')
    );
  }, { timeout: 10000 });
}

// --- Stages pipeline with mocked API ---
test.describe('Stages pipeline (mocked API)', () => {
  test('runs stage 1 and shows causal research output', async ({ page }) => {
    // Use **/api/stages so the pattern matches the full http://localhost:3000/api/stages URL
    await page.route('**/api/stages', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(STAGES_MOCK) });
    });

    await page.goto('/stages');
    await page.waitForLoadState('networkidle');
    await waitForReactHydration(page);

    await page.getByRole('button', { name: /Run Taste Compiler Pipeline/i }).click();

    // Stage panels are collapsed by default — wait for header, then expand to reveal content
    await expect(page.getByText('Causal Research')).toBeVisible({ timeout: 15000 });
    await page.getByText('Causal Research').click();
    await expect(page.getByText('consistency')).toBeVisible({ timeout: 5000 });
  });

  test('shows error panel when API returns 500', async ({ page }) => {
    await page.route('**/api/stages', async route => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'AWS credentials not configured' }) });
    });

    await page.goto('/stages');
    await page.waitForLoadState('networkidle');
    await waitForReactHydration(page);

    await page.getByRole('button', { name: /Run Taste Compiler Pipeline/i }).click();

    await expect(page.getByText('AWS credentials not configured')).toBeVisible({ timeout: 10000 });
  });

  test('pipeline button shows running state during fetch', async ({ page }) => {
    let resolve!: () => void;
    const blocker = new Promise<void>(r => { resolve = r; });

    await page.route('**/api/stages', async route => {
      await blocker;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(STAGES_MOCK) });
    });

    await page.goto('/stages');
    await page.waitForLoadState('networkidle');
    await waitForReactHydration(page);

    await page.getByRole('button', { name: /Run Taste Compiler Pipeline/i }).click();

    await expect(page.getByRole('button', { name: /Running Stage/i })).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('button', { name: /Running Stage/i })).toBeDisabled();

    resolve();
  });
});

// --- Create scorer demand estimate with mocked API ---
test.describe('Create scorer demand flow (mocked API)', () => {
  test('improve mode: shows taste research after clicking Run Taste Compiler', async ({ page }) => {
    await page.route('**/api/market-dynamics/create-scorer', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(DEMAND_MOCK) });
    });

    await page.goto('/create');
    await page.waitForLoadState('networkidle');
    await waitForReactHydration(page);

    await page.locator('input[placeholder*="trustworthy"]').fill('trustworthy');
    await page.locator('textarea').first().fill('Some reference text.');
    await page.getByRole('button', { name: /Run Taste Compiler →/i }).click();

    // Improve mode goes straight to research (no demand gate)
    await expect(page.getByRole('heading', { name: 'Taste Research' })).toBeVisible({ timeout: 10000 });
  });

  test('sell mode: shows demand estimate after clicking Estimate Demand', async ({ page }) => {
    await page.route('**/api/market-dynamics/create-scorer', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(DEMAND_MOCK) });
    });

    await page.goto('/create');
    await page.waitForLoadState('networkidle');
    await waitForReactHydration(page);

    await page.locator('button').filter({ hasText: 'Create a scorer to sell' }).click();
    await page.locator('input[placeholder*="trustworthy"]').fill('persuasive');
    await page.locator('button').filter({ hasText: /^Estimate Demand/ }).click();

    await expect(page.getByRole('heading', { name: 'Demand Preview' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Avg conversion')).toBeVisible();
    await expect(page.getByText('47%')).toBeVisible();
  });

  test('shows "Continue" gate after demand succeeds', async ({ page }) => {
    await page.route('**/api/market-dynamics/create-scorer', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(DEMAND_MOCK) });
    });

    await page.goto('/create');
    await page.waitForLoadState('networkidle');
    await waitForReactHydration(page);

    await page.locator('button').filter({ hasText: 'Create a scorer to sell' }).click();
    await page.locator('input[placeholder*="trustworthy"]').fill('persuasive');
    await page.locator('button').filter({ hasText: /^Estimate Demand/ }).click();

    await expect(page.getByRole('button', { name: 'Continue →' })).toBeVisible({ timeout: 10000 });
  });

  test('shows error when API returns 500', async ({ page }) => {
    await page.route('**/api/market-dynamics/create-scorer', async route => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'AWS credentials not configured' }) });
    });

    await page.goto('/create');
    await page.waitForLoadState('networkidle');
    await waitForReactHydration(page);

    await page.locator('button').filter({ hasText: 'Create a scorer to sell' }).click();
    await page.locator('input[placeholder*="trustworthy"]').fill('persuasive');
    await page.locator('button').filter({ hasText: /^Estimate Demand/ }).click();

    await expect(page.getByText('AWS credentials not configured')).toBeVisible({ timeout: 10000 });
  });
});

// --- Live simulation with mocked Stripe API ---
test.describe('Live simulation (mocked API)', () => {
  test('shows simulation results after clicking Run', async ({ page }) => {
    await page.route('**/api/market-dynamics/live-sim', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(LIVE_SIM_MOCK) });
    });

    await page.goto('/market-dynamics/live-sim');
    await page.waitForLoadState('networkidle');
    await waitForReactHydration(page);

    await page.getByRole('button', { name: /Run Market Test/i }).click();

    await expect(page.getByText('Personas', { exact: true })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Stripe Sessions', { exact: true })).toBeVisible();
    await expect(page.getByText('SG_003')).toBeVisible();
    await expect(page.getByText('✓ BOUGHT')).toBeVisible();
    await expect(page.getByText('✗ bounced')).toBeVisible();
  });

  test('shows Stripe session link for buyers', async ({ page }) => {
    await page.route('**/api/market-dynamics/live-sim', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(LIVE_SIM_MOCK) });
    });

    await page.goto('/market-dynamics/live-sim');
    await page.waitForLoadState('networkidle');
    await waitForReactHydration(page);

    await page.getByRole('button', { name: /Run Market Test/i }).click();

    await expect(page.getByText('Stripe Session Created')).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('link', { name: 'Open Checkout →' })).toBeVisible();
  });

  test('shows error when STRIPE_SECRET_KEY is missing', async ({ page }) => {
    await page.route('**/api/market-dynamics/live-sim', async route => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'STRIPE_SECRET_KEY not configured' }) });
    });

    await page.goto('/market-dynamics/live-sim');
    await page.waitForLoadState('networkidle');
    await waitForReactHydration(page);

    await page.getByRole('button', { name: /Run Market Test/i }).click();

    await expect(page.getByText('STRIPE_SECRET_KEY not configured')).toBeVisible({ timeout: 10000 });
  });

  test('button shows loading state during fetch', async ({ page }) => {
    let resolve!: () => void;
    const blocker = new Promise<void>(r => { resolve = r; });

    await page.route('**/api/market-dynamics/live-sim', async route => {
      await blocker;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(LIVE_SIM_MOCK) });
    });

    await page.goto('/market-dynamics/live-sim');
    await page.waitForLoadState('networkidle');
    await waitForReactHydration(page);

    await page.getByRole('button', { name: /Run Market Test/i }).click();

    await expect(page.getByRole('button', { name: /Running Market Test/i })).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('button', { name: /Running Market Test/i })).toBeDisabled();

    resolve();
  });
});
