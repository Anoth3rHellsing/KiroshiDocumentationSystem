import { test, expect } from '@playwright/test';

test('App loads and bypasses tutorial', async ({ page }) => {
  await page.goto('/');

  // Wait for the main UI to be visible.
  // We check for the 'Saved Cases' tab which is a reliable indicator that the main dashboard has loaded
  // and the tutorial overlay is not blocking the view.
  const savedCasesTab = page.getByRole('tab', { name: 'Saved Cases' }).first();
  await expect(savedCasesTab).toBeVisible({ timeout: 30000 });

  // Basic sanity check for title
  await expect(page).toHaveTitle(/Kiroshi/);
});
