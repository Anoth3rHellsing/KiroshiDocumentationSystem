import { test, expect } from '@playwright/test';

test('Sanity check: App loads and title is correct', async ({ page }) => {
  await page.goto('/');

  // Wait for the app to load - look for the main container or a specific element
  await expect(page).toHaveTitle(/Kiroshi/);

  // Check for the Dashboard tab, which should be visible
  // Using a more specific selector to avoid ambiguity
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 30000 });
});
