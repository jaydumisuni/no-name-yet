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

  await page.getByRole('button', { name: 'Mission Planner', exact: true }).first().click();
  await expect(page.locator('#llmPolicySelect')).toBeVisible();
  await expect(page.locator('#providerSelect')).toBeVisible();
  await expect(page.locator('#llmModelInput')).toBeVisible();
  await expect(page.locator('#llmBaseUrlInput')).toBeVisible();
  await expect(page.locator('#llmProtocolSelect')).toBeVisible();
  await expect(page.locator('#llmCouncilSelect')).toBeVisible();
  await expect(page.locator('#deployBtn')).toBeVisible();
  await expect(page.locator('#providerSelect')).toHaveValue('auto');
  await expect(page.locator('#llmPolicySelect')).toHaveValue('preferred');
  await expect(page.locator('#llmCouncilSelect')).toHaveValue('adaptive');

  await page.getByRole('button', { name: 'Dashboard', exact: true }).first().click();
  await expect(page.locator('#semanticRoute')).toContainText('auto');
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

test('semantic router persists an explicit FCC-compatible configuration', async ({ page }) => {
  await page.setViewportSize({ width: 1200, height: 900 });
  await page.goto(previewUrl);
  await page.evaluate(() => {
    window.__sergeantPayloads = [];
    window.sergeantHostSend = (payload) => {
      window.__sergeantPayloads.push(JSON.parse(payload));
      return true;
    };
  });

  await page.getByRole('button', { name: 'Mission Planner', exact: true }).first().click();
  await page.locator('#llmPolicySelect').selectOption('required');
  await page.locator('#providerSelect').selectOption('fcc');
  await page.locator('#llmModelInput').fill('provider/qwen3-coder-next');
  await page.locator('#llmModelInput').dispatchEvent('change');
  await page.locator('#llmBaseUrlInput').fill('http://127.0.0.1:8082/v1');
  await page.locator('#llmBaseUrlInput').dispatchEvent('change');
  await page.locator('#llmProtocolSelect').selectOption('responses');
  await page.locator('#llmCouncilSelect').selectOption('always');

  const savePayloads = await page.evaluate(() => window.__sergeantPayloads.filter((item) => item.type === 'saveSettings'));
  expect(savePayloads.length).toBeGreaterThanOrEqual(6);
  expect(savePayloads.at(-1)).toEqual({
    type: 'saveSettings',
    settings: {
      policy: 'required',
      provider: 'fcc',
      baseUrl: 'http://127.0.0.1:8082/v1',
      model: 'provider/qwen3-coder-next',
      protocol: 'responses',
      council: 'always',
    },
  });

  await expect(page.locator('#missionSummary')).toContainText('fcc · provider/qwen3-coder-next');
});

test('Command Center sends only one mission while a run is active', async ({ page }) => {
  await page.setViewportSize({ width: 1200, height: 900 });
  await page.goto(previewUrl);
  await page.evaluate(() => {
    window.__sergeantPayloads = [];
    window.sergeantHostSend = (payload) => {
      window.__sergeantPayloads.push(JSON.parse(payload));
      return true;
    };
  });

  const launchButton = page.locator('.quick-actions [data-action="reviewWorkspace"]');
  await launchButton.click();
  await expect(launchButton).toBeDisabled();

  await page.evaluate(() => {
    const button = document.querySelector('.quick-actions [data-action="reviewWorkspace"]');
    button.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
  });

  const runPayloads = await page.evaluate(() => window.__sergeantPayloads.filter((item) => item.type === 'run'));
  expect(runPayloads).toHaveLength(1);
  expect(runPayloads[0].action).toBe('reviewWorkspace');
  expect(runPayloads[0].settings).toEqual({
    policy: 'preferred',
    provider: 'auto',
    baseUrl: '',
    model: '',
    protocol: 'auto',
    council: 'adaptive',
  });

  await page.evaluate(() => {
    window.postMessage({
      type: 'sergeantState',
      state: {
        status: 'Complete',
        running: '',
        workspace: 'sergeant',
        history: [],
        settings: {
          policy: 'preferred',
          provider: 'auto',
          baseUrl: '',
          model: '',
          protocol: 'auto',
          council: 'adaptive',
        },
      },
    }, '*');
  });
  await expect(launchButton).toBeEnabled();
});
