import { test, expect } from '@playwright/test';

test('sanity check: app loads and dashboard is visible', async ({ page }) => {
  // Wait for the app to load
  await page.goto('/');

  // Wait for the "Dashboard" tab to be present
  // Streamlit tabs are often buttons with specific role and name
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });
  await expect(dashboardTab).toBeVisible({ timeout: 30000 });

  // Optional: Verify title or other key elements
  // The app title or header might be present
  // await expect(page).toHaveTitle(/Kiroshi/);
});
