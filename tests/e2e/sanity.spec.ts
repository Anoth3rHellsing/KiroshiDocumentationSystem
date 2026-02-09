import { test, expect } from '@playwright/test';

test('App load sanity check', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Kiroshi/);
});
