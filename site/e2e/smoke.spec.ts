import { expect, test, type Page } from '@playwright/test';

const APP_LAYERS = ['priority-casing', 'priority', 'lanes-protected', 'lanes-paint', 'lanes-offstreet', 'crashes', 'area-outline'];

async function mapReady(page: Page) {
  await page.waitForFunction(() => {
    const m = (window as any).__map;
    return !!m && !!m.getLayer('priority');
  });
}

async function visibleAppLayers(page: Page) {
  return page.evaluate((ids) => {
    const m = (window as any).__map;
    return ids.filter((id: string) => m.getLayer(id) && m.getLayoutProperty(id, 'visibility') !== 'none');
  }, APP_LAYERS);
}

async function openCb9(page: Page) {
  await page.goto('/#/cb/309');
  await expect(page.getByRole('heading', { name: 'Brooklyn CB 9' })).toBeVisible();
  const first = page.locator('ul.rows li').first();
  await expect(first.locator('.badge')).toHaveText('T1');
  await expect(page.locator('#map canvas').first()).toBeVisible();
  expect(page.url()).toContain('#/cb/309');
  return first;
}

test('CB 9 desktop flow', async ({ page }) => {
  const first = await openCb9(page);
  await mapReady(page);

  // Turn every layer off: no app layer stays visible.
  expect((await visibleAppLayers(page)).length).toBeGreaterThan(0);
  const boxes = page.locator('#layer-list input[type=checkbox]');
  expect(await boxes.count()).toBe(4);
  for (let i = 0; i < 4; i++) {
    const b = boxes.nth(i);
    if (await b.isEnabled()) await b.uncheck();
  }
  await expect.poll(() => visibleAppLayers(page)).toEqual([]);

  // Selecting a row opens the detail with a copy-link button.
  await first.locator('button.row').click();
  await expect(page.getByRole('button', { name: 'Copy link' })).toBeVisible();

  // Export dialog offers both report types.
  await page.locator('#export-btn').click();
  await expect(page.getByRole('button', { name: 'DOT summary' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Board view' })).toBeVisible();
});

test('unknown area falls back to citywide with a notice', async ({ page }) => {
  await page.goto('/#/cb/999');
  await expect(page.getByText('Area not found; showing citywide.')).toBeVisible();
});

test.describe('phone', () => {
  test.use({ viewport: { width: 390, height: 844 } });
  test('CB 9 with the list below the map', async ({ page }) => {
    await openCb9(page);
    const map = await page.locator('#map').boundingBox();
    const panel = await page.locator('aside.panel').boundingBox();
    expect(map && panel).toBeTruthy();
    expect(panel!.y).toBeGreaterThanOrEqual(map!.y + map!.height - 1);
  });
});
