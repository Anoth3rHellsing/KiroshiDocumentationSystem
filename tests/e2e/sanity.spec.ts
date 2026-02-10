import { test, expect } from '@playwright/test';

test('app loads and title is visible', async ({ page }) => {
  await page.goto('/');
  // Wait for the app to load
  await expect(page).toHaveTitle(/Kiroshi/i);
});
