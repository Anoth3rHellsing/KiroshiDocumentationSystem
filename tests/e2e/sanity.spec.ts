import { test, expect } from '@playwright/test';

test('sanity check: app loads and dashboard is visible', async ({ page }) => {
  // Wait for the app to load. Streamlit can take a moment.
  await page.goto('/');

  // Wait for the main app container
  await page.waitForSelector('[data-testid="stAppViewContainer"]', { timeout: 30000 });

  // Check for the "Dashboard" tab to verify the app structure loaded
  // Using getByRole is more robust for Streamlit tabs
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();

  // Optional: Check title or header
  await expect(page).toHaveTitle(/Kiroshi/);
});
