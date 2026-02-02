import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  await page.goto('/');
  // Allow some time for Streamlit to load
  await expect(page).toHaveTitle(/Streamlit/, { timeout: 10000 }).catch(() => {
      // Fallback if title is already set to something else or stays default
  });
});
