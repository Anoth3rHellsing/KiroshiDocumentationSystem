import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // This test just ensures the runner works and can reach the app.
  // The app title usually contains "Kiroshi".
  // We use a lenient check or just verify we can load the page.
  await page.goto('/');
  // Basic assertion
  await expect(page).toHaveTitle(/Kiroshi/);
});
