import { test, expect } from '@playwright/test';

test('App loads and Dashboard is visible', async ({ page }) => {
  // Wait for the main app container to ensure Streamlit has initialized
  await page.goto('/');

  // As per memory: wait for stAppViewContainer
  await page.waitForSelector('[data-testid="stAppViewContainer"]');

  // As per memory: Check for "Dashboard" tab. Streamlit tabs usually have role="tab".
  // Using exact: true as recommended in memory.
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard', exact: true });
  await expect(dashboardTab).toBeVisible();

  // As per memory: Validating 'Tracked Cases' visibility using exact match.
  // This is likely a header or text in the dashboard.
  await expect(page.getByText('Tracked Cases', { exact: true })).toBeVisible();
});
