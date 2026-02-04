import { test, expect } from '@playwright/test';

test('Sanity check: Dashboard loads', async ({ page }) => {
  await page.goto('/');

  // Wait for the main title or key element
  await expect(page).toHaveTitle(/Kiroshi/);

  // Check for the Dashboard header (use more specific locator to avoid strict mode violations)
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();

  // Check for the Recent Tracked Files section (which we just modified)
  await expect(page.locator('text=Recent Tracked Files')).toBeVisible();
});
