
import { test, expect } from '@playwright/test';

test('App loads and dashboard is visible', async ({ page }) => {
  await page.goto('/');

  // Wait for the main Streamlit container to appear
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible({ timeout: 15000 });

  // Verify the title
  await expect(page).toHaveTitle(/Kiroshi/);

  // Verify the Dashboard tab is present
  // Using getByRole as per memory to avoid strict mode violations
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
