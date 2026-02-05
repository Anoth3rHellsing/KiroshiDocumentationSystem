import { test, expect } from '@playwright/test';

test('sanity check - app loads', async ({ page }) => {
  await page.goto('/');
  // Wait for the Dashboard tab to be visible, which confirms the app loaded
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 15000 });
});
