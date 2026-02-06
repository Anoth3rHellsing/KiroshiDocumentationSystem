import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  await page.goto('/');
  // Wait for the app to load. The dashboard tab is a good indicator.
  // We use a regex for loose matching or exact name if known.
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 30000 });
});
