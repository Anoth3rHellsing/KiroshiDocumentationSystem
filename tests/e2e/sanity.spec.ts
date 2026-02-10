import { test, expect } from '@playwright/test';

test('App loads and shows Dashboard', async ({ page }) => {
  await page.goto('/');
  // Wait for the main app container to be visible
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible();

  // Verify the Dashboard tab is present
  // Using exact: true to avoid matching potential "Dashboard" text elsewhere
  await expect(page.getByRole('tab', { name: 'Dashboard', exact: true })).toBeVisible();
});
