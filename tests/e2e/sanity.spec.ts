import { test, expect } from '@playwright/test';

test('app should load and have correct title', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Kiroshi Documentation System/);
});
