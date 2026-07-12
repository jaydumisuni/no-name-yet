const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');

const preview = process.env.COMMAND_CENTER_PREVIEW || path.join(process.cwd(), 'build', 'command-center-preview.html');
const previewUrl = pathToFileURL(preview).href;
const pages = [
  ['Dashboard', 'dashboard'],
  ['Mission Planner', 'orders'],
  ['Evidence', 'evidence'],
  ['Evidence Locker', 'reports'],
  ['Officers / Armoury', 'squad'],
  ['Settings', 'settings'],
  ['Doctrine', 'doctrine'],
  ['Roadmap', 'roadmap'],
  ['Guide', 'guide'],
];

async function assertCommandCenter(page, screenshotName) {
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  await page.goto(previewUrl);
  await expect(page.locator('h1')).toContainText('SGT');
  await expect(page.locator('#dashboardOfficers .officer')).toHaveCount(5);
  for (const [label, id] of pages) {
    await page.getByRole('button', { name: label, exact: true }).first().click();
    await expect(page.locator(`#${id}`)).toBeVisible();
  }
  await expect(page.locator('#providerSelect')).toBeVisible();
  await page.locator('[data-page="dashboard"]').first().click();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(2);
  expect(pageErrors).toEqual([]);
  await page.screenshot({ path: path.join('artifacts', screenshotName), fullPage: true });
}

test('full Command Center renders and navigates', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await assertCommandCenter(page, 'command-center-1600.png');
});

test('compact IDE width remains usable', async ({ page }) => {
  await page.setViewportSize({ width: 420, height: 920 });
  await assertCommandCenter(page, 'command-center-420.png');
});
