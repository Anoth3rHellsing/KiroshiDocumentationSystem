import { test, expect } from '@playwright/test';

test('sanity check: app loads and dashboard is visible', async ({ page }) => {
  // Navigate to the app root
  await page.goto('/');

  // Wait for the main app container to ensure Streamlit has mounted
  await page.waitForSelector('.stApp');

  // Verify the page title (Streamlit default or custom)
  await expect(page).toHaveTitle(/Kiroshi/);

  // Verify the Dashboard tab is present
  // Using getByRole with name as per memory guidelines
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
