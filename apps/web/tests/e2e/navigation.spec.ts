import { test, expect } from '@playwright/test';

const ROUTES = [
  { path: '/', heading: 'Go against AI slop. Monetize your taste.' },
  { path: '/runs/demo', heading: null },
  { path: '/stages', heading: 'Live Pipeline Proof' },
  { path: '/create', heading: 'Create a Scorer' },
  { path: '/market-dynamics', heading: null },
  { path: '/market-dynamics/marketplace', heading: null },
  { path: '/market-dynamics/simulations', heading: null },
  { path: '/market-dynamics/live-sim', heading: 'Nemotron Persona → Stripe Simulation' },
  { path: '/market-dynamics/methodology', heading: null },
  { path: '/market-dynamics/dashboard', heading: null },
];

for (const { path, heading } of ROUTES) {
  test(`${path} loads without error`, async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });

    const response = await page.goto(path);
    expect(response?.status()).toBeLessThan(400);

    await page.waitForLoadState('networkidle');

    if (heading) {
      await expect(page.getByRole('heading', { name: heading })).toBeVisible();
    } else {
      await expect(page.locator('h1, h2').first()).toBeVisible();
    }

    const jsErrors = errors.filter(e =>
      !e.includes('favicon') &&
      !e.includes('404') &&
      !e.includes('hot-reload')
    );
    expect(jsErrors, `Console errors on ${path}: ${jsErrors.join(', ')}`).toHaveLength(0);
  });
}

test('no dead internal links on home page', async ({ page }) => {
  await page.goto('/');
  await page.waitForLoadState('networkidle');

  const links = await page.locator('a[href^="/"]').all();
  for (const link of links) {
    const href = await link.getAttribute('href');
    if (!href) continue;
    const res = await page.request.get(href);
    expect(res.status(), `Dead link: ${href}`).toBeLessThan(400);
  }
});

test('no dead internal links on market-dynamics index', async ({ page }) => {
  await page.goto('/market-dynamics');
  await page.waitForLoadState('networkidle');

  const links = await page.locator('a[href^="/"]').all();
  for (const link of links) {
    const href = await link.getAttribute('href');
    if (!href) continue;
    const res = await page.request.get(href);
    expect(res.status(), `Dead link: ${href}`).toBeLessThan(400);
  }
});
