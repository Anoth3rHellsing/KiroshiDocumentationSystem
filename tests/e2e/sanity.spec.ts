import { test, expect } from '@playwright/test';

test('app loads and displays dashboard', async ({ page }) => {
  await page.goto('/');

  // Wait for the app to initialize (Streamlit loading)
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible({ timeout: 45000 });

  // Check for the "Dashboard" tab which is selected by default
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
