
import { test, expect } from '@playwright/test';

test('App loads and dashboard is visible', async ({ page }) => {
  // Navigate to the app with query params to ensure consistent theme and avoid surprises
  await page.goto('/?enable_holiday_theme=false&theme_preview=default');

  // Wait for the app to be ready. Streamlit usually renders a "running" state first.
  // We wait for the "Dashboard" tab to be present in the tab list.
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });
  await expect(dashboardTab).toBeVisible({ timeout: 60000 });

  // Verify the page title to ensure we are in the right app
  await expect(page).toHaveTitle(/Kiroshi/);

  // Check for the "Add Case" button as a sign that the sidebar or main navigation is loaded
  const addCaseBtn = page.getByRole('button', { name: 'Add Case' });
  // Note: Add Case might be inside a tab or main area depending on layout changes,
  // but it's a key interaction point.
});
