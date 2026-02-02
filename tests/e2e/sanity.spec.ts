import { test, expect } from '@playwright/test';

test('Sanity check - App loads', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Kiroshi/);
});
