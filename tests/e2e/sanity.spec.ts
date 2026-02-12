import { test, expect } from '@playwright/test';

test('App sanity check - loads dashboard', async ({ page }) => {
  // Wait for the app to load
  await page.goto('/');

  // Streamlit apps usually have a title or some element we can check.
  // Based on previous verification scripts, we know it loads.
  // Let's check for a common element or just the title.
  await expect(page).toHaveTitle(/Kiroshi/);

  // Check for the "Dashboard" tab or similar if possible,
  // but title check is a good start for a sanity test.
  // The tab list usually has role="tab".
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' }).first();
  await expect(dashboardTab).toBeVisible();
});
