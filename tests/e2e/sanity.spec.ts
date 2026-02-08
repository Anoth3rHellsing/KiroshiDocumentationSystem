import { test, expect } from '@playwright/test';

test('App sanity check', async ({ page }) => {
  await page.goto('/');

  // Wait for the app container to load
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible({ timeout: 30000 });

  // Verify the Dashboard tab exists using a role locator to be robust
  // Using { exact: true } helps avoid partial matches if needed, but per memory:
  // "checking for the 'Dashboard' tab using `page.getByRole('tab', { name: 'Dashboard' })`"
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
