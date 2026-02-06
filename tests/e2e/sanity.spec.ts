import { test, expect } from '@playwright/test';

test('sanity check: app loads and dashboard is visible', async ({ page }) => {
  await page.goto('/');

  // Streamlit tabs are buttons with role 'tab'
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });

  // Increase timeout as Streamlit startup can be slow in CI
  await expect(dashboardTab).toBeVisible({ timeout: 45000 });

  // Verify title
  await expect(page).toHaveTitle(/Kiroshi/);
});
