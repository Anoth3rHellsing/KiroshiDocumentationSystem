import { test, expect } from '@playwright/test';

test('Sanity check: Dashboard loads', async ({ page }) => {
  await page.goto('/');

  // Wait for the app container
  await page.waitForSelector('.stApp', { timeout: 30000 });

  // Verify Dashboard tab exists
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
