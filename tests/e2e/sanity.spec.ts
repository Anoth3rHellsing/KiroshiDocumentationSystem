import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  await page.goto('/');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/Kiroshi/);

  // Wait for the app to be ready (look for a known element)
  // e.g. the "Add Case" button or the Dashboard tab
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 30000 });
});
