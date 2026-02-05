import { test, expect } from '@playwright/test';

test('App loads and title is correct', async ({ page }) => {
  // Go to the app
  await page.goto('/');

  // Wait for title to be set (Streamlit sets it dynamically)
  await expect(page).toHaveTitle(/Kiroshi/);

  // Check for some basic element to ensure it rendered
  // Using a broad check like looking for the main container or sidebar
  await expect(page.getByTestId('stSidebar')).toBeVisible();
});
