import { test, expect } from '@playwright/test';

test('App loads and dashboard is visible', async ({ page }) => {
  // Go to the app
  await page.goto('/');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/Kiroshi/);

  // Check for the Dashboard tab. Using .first() as per guidelines for Streamlit tabs which might have duplicates in DOM.
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' }).first();
  await expect(dashboardTab).toBeVisible({ timeout: 60000 });
});
