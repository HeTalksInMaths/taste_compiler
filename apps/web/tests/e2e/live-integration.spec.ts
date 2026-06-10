import { test, expect } from '@playwright/test';

// Live integration tests — hit real AWS Bedrock, Stripe (test mode), and Exa.
// Require .env.local to be populated. Longer timeouts for real API latency.

test.describe('Live: /api/stages (Bedrock + Exa)', () => {
  test('stage 1 returns causal research from real Bedrock', async ({ page }) => {
    await page.goto('/stages');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: 'concise' }).click();
    await page.getByRole('button', { name: /Run Full Pipeline/i }).click();

    // Stage 1 panel appears immediately when running starts
    await expect(page.getByText('Stage 1 — Causal Research')).toBeVisible({ timeout: 10000 });

    // Wait for the loading text to disappear — means stage 1 got a response
    await expect(page.getByText('Searching web')).not.toBeVisible({ timeout: 90000 });

    // Stage 1 panel should now show real content (not loading state)
    // The running button will have moved to "Running Stage 2/8..."
    await expect(page.getByText('Stage 1 — Causal Research')).toBeVisible();
    // Stage 2 should have started (proves stage 1 returned data)
    await expect(page.getByText('Stage 2 — Causal Graph')).toBeVisible({ timeout: 5000 });
  }, { timeout: 120000 });
});

test.describe('Live: /api/market-dynamics/create-scorer (demand — no Bedrock)', () => {
  test('demand estimate runs without Bedrock (deterministic)', async ({ page }) => {
    await page.goto('/create');
    await page.waitForLoadState('networkidle');

    await page.locator('input[placeholder*="urgent"]').fill('concise');
    await page.getByRole('button', { name: /Estimate Demand/i }).click();

    // Demand step is deterministic (no Bedrock) — should be fast
    await expect(page.getByRole('heading', { name: 'Demand Estimate' })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('Avg conversion')).toBeVisible();
    await expect(page.getByText('Revenue / 100')).toBeVisible();
  });
});

test.describe('Live: /api/market-dynamics/live-sim (Stripe test mode)', () => {
  test('simulation creates real Stripe test sessions', async ({ page }) => {
    await page.goto('/market-dynamics/live-sim');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /Run Live Simulation/i }).click();

    // Wait for the button to re-enable — simulation complete
    await expect(page.getByRole('button', { name: /Run Live Simulation/i })).toBeEnabled({ timeout: 30000 });

    // Stats grid — use exact: true to avoid matching description paragraph text
    await expect(page.getByText('Personas', { exact: true })).toBeVisible();
    await expect(page.getByText('Buyers', { exact: true })).toBeVisible();
    await expect(page.getByText('Conversion', { exact: true })).toBeVisible();
    await expect(page.getByText('Stripe Sessions', { exact: true })).toBeVisible();

    // Persona cards rendered
    const personaCards = page.locator('.glass-card').filter({ hasText: /BOUGHT|bounced/ });
    await expect(personaCards.first()).toBeVisible();
  }, { timeout: 60000 });
});

test.describe('Live: /api/chat (AI Gateway)', () => {
  test('chat route returns a stream without error', async ({ request }) => {
    const response = await request.post('/api/chat', {
      headers: { 'Content-Type': 'application/json' },
      data: { messages: [{ role: 'user', content: 'Say "ok" and nothing else.' }] },
      timeout: 30000,
    });

    // 200 = streaming started; not 400/500
    expect(response.status()).toBe(200);
  }, { timeout: 45000 });

  test('chat route rejects empty messages array with 400', async ({ request }) => {
    const response = await request.post('/api/chat', {
      headers: { 'Content-Type': 'application/json' },
      data: {},
    });
    expect(response.status()).toBe(400);
    const body = await response.json();
    expect(body.error).toMatch(/messages/i);
  });
});
