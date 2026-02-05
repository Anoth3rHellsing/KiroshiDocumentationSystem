import { test, expect } from '@playwright/test';

test('App loads successfully and displays Dashboard', async ({ page }) => {
  await page.goto('/');

  // Wait for the app title to be correct
  await expect(page).toHaveTitle(/Kiroshi/);

  // Wait for the Dashboard tab to be visible, ensuring the app has initialized
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });
  await expect(dashboardTab).toBeVisible({ timeout: 30000 });
});
