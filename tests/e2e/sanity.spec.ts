import { test, expect } from '@playwright/test';

test('app loads and dashboard is visible', async ({ page }) => {
  await page.goto('/');

  // Wait for the main app container to ensure Streamlit has loaded
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible({ timeout: 45000 });

  // Verify the Dashboard tab is present
  // Use getByRole to avoid strict mode violations if 'Dashboard' appears elsewhere
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
