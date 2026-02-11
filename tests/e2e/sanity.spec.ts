import { test, expect } from '@playwright/test';

test('app loads and displays title', async ({ page }) => {
  await page.goto('/');
  // Wait for the app to load
  await expect(page).toHaveTitle(/Kiroshi/);
  // Verify basic structure
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
