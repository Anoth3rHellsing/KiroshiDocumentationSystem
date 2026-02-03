import { test, expect } from '@playwright/test';

test('app loads and shows title', async ({ page }) => {
  // Increase timeout for initial load as Streamlit can be slow to start
  test.setTimeout(60000);

  await page.goto('/');

  // Wait for the app to be ready (Streamlit often changes the title dynamically)
  // We expect "Kiroshi" to appear in the title eventually.
  await expect(page).toHaveTitle(/Kiroshi/i, { timeout: 30000 });
});
