import { test, expect } from '@playwright/test';

test('App loads and dashboard is visible', async ({ page }) => {
  await page.goto('/');

  // Wait for the main app container
  await expect(page.locator('.stApp')).toBeVisible({ timeout: 30000 });

  // Check for the Dashboard tab using a robust locator
  // st.tabs generates buttons with role="tab"
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });
  await expect(dashboardTab).toBeVisible();
});
