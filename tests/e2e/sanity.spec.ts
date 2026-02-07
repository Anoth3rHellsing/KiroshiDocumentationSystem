import { test, expect } from '@playwright/test';

test('sanity check: app loads and dashboard is visible', async ({ page }) => {
  // Go to the app (baseURL is set in config)
  await page.goto('/');

  // Wait for the app to load. Streamlit usually puts "running" or skeleton elements.
  // We'll wait for the "Dashboard" tab to verify the main UI structure.
  // Note: Streamlit tabs are often buttons with role="tab".
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });

  await expect(dashboardTab).toBeVisible({ timeout: 60000 });

  // Verify title (optional, based on app content)
  await expect(page).toHaveTitle(/Kiroshi/);
});
