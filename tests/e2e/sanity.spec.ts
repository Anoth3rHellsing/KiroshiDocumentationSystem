import { test, expect } from '@playwright/test';

test('App loads and dashboard is visible', async ({ page }) => {
  // Go to the app
  await page.goto('/');

  // Wait for title to be set (Streamlit sets it dynamically)
  await expect(page).toHaveTitle(/Kiroshi/);

  // Check for the Dashboard tab.
  // This verifies that the main app UI has loaded and passed the tutorial/initialization.
  // Note: Streamlit tabs are often buttons with role="tab"
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
