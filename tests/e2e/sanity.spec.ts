import { test, expect } from '@playwright/test';

test('App sanity check', async ({ page }) => {
  // Wait for the main app container to ensure Streamlit has loaded
  await page.goto('/');
  await page.waitForSelector('[data-testid="stAppViewContainer"]', { timeout: 60000 });

  // Basic check for title or key element to confirm app is running
  // The dashboard title is rendered as an HTML div with class 'dashboard-title'
  // or we can look for the main tab navigation

  // Using a more generic wait to ensure the app is interactive
  await expect(page).toHaveTitle(/Kiroshi/);

  // Check for the "Dashboard" tab which should be present by default
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });
  await expect(dashboardTab).toBeVisible();
});
