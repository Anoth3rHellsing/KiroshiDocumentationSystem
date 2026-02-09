import { test, expect } from '@playwright/test';

test('sanity check: app loads and dashboard is visible', async ({ page }) => {
  await page.goto('/');

  // Wait for the main app container
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible({ timeout: 30000 });

  // Check for the "Dashboard" tab
  // Using a loose match or role to avoid strict mode issues if multiple elements match text
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
