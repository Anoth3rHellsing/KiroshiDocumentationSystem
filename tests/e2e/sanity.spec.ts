import { test, expect } from '@playwright/test';

test('Sanity check: Application loads', async ({ page }) => {
  await page.goto('/');

  // Wait for the main app container to ensure Streamlit has loaded
  await page.waitForSelector('[data-testid="stAppViewContainer"]', { timeout: 30000 });

  // Verify the title or a key element to confirm the app is rendering
  // Using a broad check first to avoid strict mode issues if multiple 'Dashboard' texts exist
  await expect(page).toHaveTitle(/Kiroshi/);

  // Check for the Dashboard tab specifically
  // Use getByRole which is more resilient than text selectors
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
