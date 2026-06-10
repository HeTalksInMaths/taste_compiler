import { test, expect } from '@playwright/test';

// Full-page screenshots for visual regression testing.
// First run creates baselines in tests/e2e/__snapshots__/.
// Subsequent runs diff against them (maxDiffPixels: 100 from config).

const STATIC_ROUTES = [
  { name: 'home', path: '/' },
  { name: 'runs-demo', path: '/runs/demo' },
  { name: 'stages', path: '/stages' },
  { name: 'create', path: '/create' },
  { name: 'market-dynamics', path: '/market-dynamics' },
  { name: 'market-dynamics-live-sim', path: '/market-dynamics/live-sim' },
  { name: 'market-dynamics-methodology', path: '/market-dynamics/methodology' },
  { name: 'market-dynamics-dashboard', path: '/market-dynamics/dashboard' },
  { name: 'market-dynamics-marketplace', path: '/market-dynamics/marketplace' },
  { name: 'market-dynamics-simulations', path: '/market-dynamics/simulations' },
];

for (const { name, path } of STATIC_ROUTES) {
  test(`screenshot: ${name}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    // Wait for fonts and any animations to settle
    await page.waitForTimeout(300);
    await expect(page).toHaveScreenshot(`${name}.png`, { fullPage: true });
  });
}

// Screenshot after a mocked API response to capture result state
test('screenshot: stages after stage 1 result', async ({ page }) => {
  await page.route('/api/stages', async route => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        stage: 1, target_variable: 'trustworthy', search_results: [], model: 'mock',
        result: { target_variable: 'trustworthy', causal_research: [{ source_id: 'SRC_001', claim: 'Consistent messaging builds trust.', causal_variable: 'consistency', effect_direction: 'increases', mechanism: 'Predictability reduces uncertainty.', evidence_strength: 'high' }], research_tensions: [] },
      }),
    });
  });

  await page.goto('/stages');
  await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: /Run Full Pipeline/i }).click();
  await expect(page.getByText('consistency')).toBeVisible({ timeout: 10000 });
  await expect(page).toHaveScreenshot('stages-after-stage1.png', { fullPage: true });
});

test('screenshot: create after demand estimate', async ({ page }) => {
  await page.route('/api/market-dynamics/create-scorer', async route => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        step: 'demand',
        result: {
          segment_demand: [
            { segment: 'startup_founder_operator', label: 'Startup Founder', base_intent: 0.72, reveal_probability: 0.45, estimated_buyers_per_100: 45 },
            { segment: 'marketing_growth_lead', label: 'Marketing / Growth', base_intent: 0.78, reveal_probability: 0.50, estimated_buyers_per_100: 50 },
          ],
          avg_conversion_rate: 0.47, estimated_revenue_per_100_personas: 235, estimated_platform_take: 49,
        },
      }),
    });
  });

  await page.goto('/create');
  await page.locator('input[placeholder*="urgent"]').fill('trustworthy');
  await page.getByRole('button', { name: /Estimate Demand/i }).click();
  await expect(page.getByText('Demand Estimate')).toBeVisible({ timeout: 10000 });
  await expect(page).toHaveScreenshot('create-after-demand.png', { fullPage: true });
});
