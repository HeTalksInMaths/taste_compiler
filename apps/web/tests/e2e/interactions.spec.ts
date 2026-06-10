import { test, expect, type Page } from '@playwright/test';

// Next.js 14 App Router fires `networkidle` before React finishes hydrating.
// Without this wait, click/fill events land before React attaches handlers
// and are silently dropped (state never updates). 500ms is sufficient locally.
async function waitForReact(page: Page) {
  // React 18 marks fiber properties non-enumerable, so Object.keys misses them.
  // Object.getOwnPropertyNames returns all own properties including non-enumerable.
  await page.waitForFunction(() => {
    const el = document.querySelector('button');
    if (!el) return false;
    return Object.getOwnPropertyNames(el).some(
      k => k.startsWith('__reactFiber') || k.startsWith('__reactProps')
    );
  }, { timeout: 10000 });
}

// --- Home page ---
test.describe('Home page interactions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('heading and tagline are visible', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Go against AI slop/i })).toBeVisible();
    await expect(page.getByText(/Taste Compiler helps you define/)).toBeVisible();
  });

  test('"Improve Text or Create Scorer" CTA navigates to /create', async ({ page }) => {
    await page.getByRole('link', { name: /Improve Text or Create Scorer/i }).click();
    await page.waitForURL('**/create');
    expect(page.url()).toContain('/create');
  });

  test('"View Demo Run" CTA navigates to /runs/demo', async ({ page }) => {
    await page.getByRole('link', { name: 'View Demo Run' }).click();
    await page.waitForURL('**/runs/demo');
    expect(page.url()).toContain('/runs/demo');
  });

  test('"Inspect live pipeline" link navigates to /stages', async ({ page }) => {
    await page.getByRole('link', { name: /Inspect live pipeline/i }).click();
    await page.waitForURL('**/stages');
    expect(page.url()).toContain('/stages');
  });

  test('all 3 "how it works" cards are visible', async ({ page }) => {
    await expect(page.getByText('1. Define quality')).toBeVisible();
    await expect(page.getByText('2. Generate and test')).toBeVisible();
    await expect(page.getByText('3. Market-test and sell')).toBeVisible();
  });
});

// --- Stages page ---
test.describe('Stages page interactions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/stages');
    await page.waitForLoadState('networkidle');
    await waitForReact(page);
  });

  test('all 8 variable buttons are visible and clickable', async ({ page }) => {
    const variables = ['trustworthy', 'persuasive', 'concise', 'urgent', 'funny', 'professional', 'empathetic', 'data-driven'];
    for (const v of variables) {
      const btn = page.getByRole('button', { name: v });
      await expect(btn).toBeVisible();
      await btn.click();
    }
  });

  test('clicking a variable highlights it with active style', async ({ page }) => {
    await page.getByRole('button', { name: 'persuasive' }).click();
    const btn = page.getByRole('button', { name: 'persuasive' });
    // React converts #4c6ef5 to rgb(76, 110, 245) in the browser
    await expect(btn).toHaveCSS('background-color', 'rgb(76, 110, 245)');
  });

  test('"Run Taste Compiler Pipeline" button is visible and enabled', async ({ page }) => {
    const btn = page.getByRole('button', { name: /Run Taste Compiler Pipeline/i });
    await expect(btn).toBeVisible();
    await expect(btn).toBeEnabled();
  });
});

// --- Create scorer page ---
test.describe('Create scorer page interactions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/create');
    await page.waitForLoadState('networkidle');
    await waitForReact(page);
  });

  test('mode toggle buttons are visible', async ({ page }) => {
    await expect(page.getByText('Improve my text')).toBeVisible();
    await expect(page.getByText('Create a scorer to sell')).toBeVisible();
  });

  test('switching to "sell" mode shows audience and price sections', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'Create a scorer to sell' }).click();
    await expect(page.getByText('Audience', { exact: true })).toBeVisible();
    await expect(page.getByText('Reveal Price', { exact: true })).toBeVisible();
  });

  test('goal suggestion chips set the input', async ({ page }) => {
    for (const goal of ['persuasive', 'trustworthy', 'funny']) {
      await page.locator('button').filter({ hasText: goal }).first().click();
      await expect(page.locator('input[placeholder*="trustworthy"]')).toHaveValue(goal);
    }
  });

  test('"Run Taste Compiler" button disabled when no input (improve mode)', async ({ page }) => {
    const btn = page.getByRole('button', { name: /Run Taste Compiler →/i });
    await expect(btn).toBeDisabled();
  });

  test('"Run Taste Compiler" enables after entering goal and reference text', async ({ page }) => {
    await page.locator('input[placeholder*="trustworthy"]').fill('trustworthy');
    await page.locator('textarea').first().fill('Some reference text to improve.');
    await expect(page.getByRole('button', { name: /Run Taste Compiler →/i })).toBeEnabled();
  });

  test('"Estimate Demand" button appears in sell mode', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'Create a scorer to sell' }).click();
    await page.locator('input[placeholder*="trustworthy"]').fill('persuasive');
    await expect(page.locator('button').filter({ hasText: /^Estimate Demand/ })).toBeVisible();
  });

  test('sell mode: all 5 price buttons are clickable', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'Create a scorer to sell' }).click();
    for (const price of ['$2.99', '$4.99', '$6.99', '$9.99', '$14.99']) {
      await page.getByRole('button', { name: price }).click();
    }
  });

  test('sell mode: segment toggle buttons work', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'Create a scorer to sell' }).click();
    const btn = page.getByRole('button', { name: 'SME Owner/Operator' });
    await expect(btn).toBeVisible({ timeout: 5000 });
    await btn.click();
    await btn.click();
    await expect(btn).toBeVisible();
  });
});

// --- Market Dynamics index ---
test.describe('Market Dynamics index', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/market-dynamics');
    await page.waitForLoadState('networkidle');
  });

  test('heading and subtitle are correct', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Market', exact: true })).toBeVisible();
    await expect(page.getByText('Before selling a scorer')).toBeVisible();
  });

  test('all 5 section cards are visible', async ({ page }) => {
    for (const title of ['Scorer Marketplace', 'Persona Market Simulation', 'Market Test', 'Methodology', 'Platform Dashboard']) {
      await expect(page.getByRole('heading', { name: title })).toBeVisible();
    }
  });

  test('"Create Your Own Scorer" link navigates to /create', async ({ page }) => {
    await page.getByRole('link', { name: /Create Your Own Scorer/i }).click();
    await page.waitForURL('**/create');
    expect(page.url()).toContain('/create');
  });

  test('section cards navigate to correct sub-routes', async ({ page }) => {
    const cards = [
      { name: 'Scorer Marketplace', url: '/market-dynamics/marketplace' },
      { name: 'Market Test', url: '/market-dynamics/live-sim' },
      { name: 'Methodology', url: '/market-dynamics/methodology' },
    ];
    for (const { name, url } of cards) {
      await page.goto('/market-dynamics');
      await page.getByRole('heading', { name }).click();
      await page.waitForURL(`**${url}`);
      expect(page.url()).toContain(url);
    }
  });
});
