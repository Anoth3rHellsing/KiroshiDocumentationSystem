import { test, expect } from '@playwright/test';

test('sanity check: app loads and dashboard is visible', async ({ page }) => {
  // Wait for the app to load
  await page.goto('/');

  // Wait for the main container or specific element to be visible
  // Using a broad timeout because first load can be slow
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 30000 });

  // Check title
  await expect(page).toHaveTitle(/Kiroshi/);

  // Take a screenshot for debugging if needed
  // await page.screenshot({ path: 'sanity-check.png' });
});
