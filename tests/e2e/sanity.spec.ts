import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  await page.goto('/');
  // Wait for the title to be correct, handling potential redirects or loading states
  await expect(page).toHaveTitle(/Kiroshi/);
});
