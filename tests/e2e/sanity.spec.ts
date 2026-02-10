import { test, expect } from '@playwright/test';

test('Application loads and Dashboard is visible', async ({ page }) => {
  // Wait for the app to load
  await page.goto('/');

  // Wait for the main container
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible({ timeout: 30000 });

  // Check for the Dashboard tab
  // Using exact: true to avoid ambiguity if "Dashboard" appears elsewhere
  await expect(page.getByRole('tab', { name: 'Dashboard', exact: true })).toBeVisible();
});
