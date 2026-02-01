import { test, expect } from '@playwright/test';

test('Sanity check - App loads', async ({ page }) => {
  // Just navigate to the base URL and check the title to ensure connectivity
  await page.goto('/');
  await expect(page).toHaveTitle(/Kiroshi/);
});
