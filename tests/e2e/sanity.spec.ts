import { test, expect } from '@playwright/test';

test('sanity check - app loads', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Kiroshi/);
});
