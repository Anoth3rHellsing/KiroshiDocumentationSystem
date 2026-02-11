import { test, expect } from '@playwright/test';

test('App loads successfully', async ({ page }) => {
  // Basic sanity check to ensure the app server is reachable
  await page.goto('/');

  // Wait for the main app container to appear (Streamlit specific)
  // This confirms the frontend loaded the Streamlit framework
  await expect(page.getByRole('tab', { name: 'Dashboard' }).first()).toBeVisible({ timeout: 15000 });
});
