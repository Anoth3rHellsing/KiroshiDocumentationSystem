import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // Just a placeholder test to ensure runner works
  await page.goto('/');

  // Expect title to contain Kiroshi (case insensitive)
  // toHaveTitle waits and retries, handling Streamlit's initial loading state
  await expect(page).toHaveTitle(/Kiroshi/i);
});
