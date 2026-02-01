import { test, expect } from '@playwright/test';

test('basic sanity check', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Kiroshi/);
});
