import { test, expect } from '@playwright/test';

test('App loads and Dashboard is visible', async ({ page }) => {
  // Go to the app URL
  await page.goto('/');

  // Wait for the app to load (look for the "Dashboard" tab)
  // We use a generous timeout because Streamlit cold start can be slow
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });
  await expect(dashboardTab).toBeVisible({ timeout: 30000 });

  // Optional: Check if main content area is visible
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible();
});
