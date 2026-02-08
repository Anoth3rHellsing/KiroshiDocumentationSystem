import { test, expect } from '@playwright/test';

test('sanity check: app loads and dashboard is visible', async ({ page }) => {
  await page.goto('/');

  // Wait for the main app container to ensure Streamlit has loaded
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible({ timeout: 30000 });

  // Check for the Dashboard tab using a robust locator as per memory
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();

  // Optional: Check for page title or header
  await expect(page).toHaveTitle(/Kiroshi/);
});
