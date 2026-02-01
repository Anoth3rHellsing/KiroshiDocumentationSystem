import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // This is a placeholder sanity check to ensure the runner finds tests
  await page.goto('/');
  await expect(page).toHaveTitle(/Kiroshi/);
});
