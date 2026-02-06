import { test, expect } from '@playwright/test';

test('App loads and dashboard is visible', async ({ page }) => {
  await page.goto('/');

  // Wait for the app to load (look for dashboard tab)
  // Streamlit apps can be slow to load initially
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 60000 });

  // Verify title
  await expect(page).toHaveTitle(/Kiroshi/);
});
