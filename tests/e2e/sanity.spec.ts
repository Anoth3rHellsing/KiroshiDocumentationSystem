import { test, expect } from '@playwright/test';

test('sanity check: app loads and dashboard is visible', async ({ page }) => {
  console.log('Navigating to app root...');
  await page.goto('/');

  // Streamlit apps can be slow to initialize. Wait for the main ready state if possible,
  // or just wait for the element we expect.
  try {
    await page.waitForSelector('[data-test-script-state="done"]', { timeout: 30000 });
  } catch (e) {
    console.warn('Timed out waiting for data-test-script-state="done". Attempting to find Dashboard tab anyway.');
  }

  // Look for the Dashboard tab
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });
  await expect(dashboardTab).toBeVisible({ timeout: 30000 });
});
