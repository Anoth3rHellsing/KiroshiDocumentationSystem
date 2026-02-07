import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // Navigate to the app (baseURL is set in config)
  await page.goto('/');

  // Wait for the main app container to ensure Streamlit loaded
  // Streamlit uses data-testid="stAppViewContainer" for the main view
  await expect(page.locator('[data-testid="stAppViewContainer"]')).toBeVisible({ timeout: 60000 });

  // Verify the 'Dashboard' tab is present, indicating the app initialized correctly
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
