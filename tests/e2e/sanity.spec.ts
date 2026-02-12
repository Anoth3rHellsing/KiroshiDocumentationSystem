import { test, expect } from '@playwright/test';

test('App loads successfully', async ({ page }) => {
  // Simple sanity check to ensure the app server is reachable and renders
  await page.goto('/');
  await expect(page).toHaveTitle(/Kiroshi/);

  // Wait for the main app container to ensure Streamlit loaded
  await expect(page.getByRole('tab', { name: 'Dashboard' }).first()).toBeVisible({ timeout: 30000 });
});
