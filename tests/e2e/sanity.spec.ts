import { test, expect } from '@playwright/test';

test('app loads and dashboard is visible', async ({ page }) => {
  await page.goto('/');

  // Wait for the app to load
  // We check for the 'Saved Cases' tab or 'Dashboard'
  // Using .first() as per memory to avoid strict mode violations if multiple exist
  await expect(page.getByRole('tab', { name: 'Dashboard' }).first()).toBeVisible({ timeout: 30000 });

  // Check if "Saved Cases" tab exists
  await expect(page.getByRole('tab', { name: 'Saved Cases' }).first()).toBeVisible();
});
