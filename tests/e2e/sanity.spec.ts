import { test, expect } from '@playwright/test';

test('should load dashboard', async ({ page }) => {
  await page.goto('/');

  // Wait for the app to load
  // We look for the "Dashboard" tab which signifies the main UI is ready
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });
  await expect(dashboardTab).toBeVisible({ timeout: 30000 });
});
