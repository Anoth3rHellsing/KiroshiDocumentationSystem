
import { test, expect } from '@playwright/test';

test('Sanity check - App Loads', async ({ page }) => {
  await page.goto('/');
  // Wait for title to be something reasonable or just check it loads
  // Using a generic assertion that likely passes if the app is running
  await expect(page).toHaveTitle(/Kiroshi/i);
});
