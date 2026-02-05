import { test, expect } from '@playwright/test';

test('App loads and Dashboard is visible', async ({ page }) => {
  await page.goto('/');

  // Wait for the app to initialize (Streamlit loading)
  // Use a longer timeout as Streamlit can take a moment to boot up the frontend
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 60000 });
});
