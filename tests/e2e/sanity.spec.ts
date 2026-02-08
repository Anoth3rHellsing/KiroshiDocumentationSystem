import { test, expect } from '@playwright/test';

test('sanity check: app loads and dashboard is visible', async ({ page }) => {
  await page.goto('/');

  // Wait for the main app container
  await page.waitForSelector('.stApp');

  // Verify Dashboard tab is present
  await expect(page.getByRole('tab', { name: 'Dashboard', exact: true })).toBeVisible();

  // Verify dashboard title using filter to avoid strict mode violation
  await expect(page.locator('.dashboard-title').filter({ hasText: 'Dashboard' })).toBeVisible();
});
