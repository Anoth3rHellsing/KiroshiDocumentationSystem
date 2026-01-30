import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // This test expects the Streamlit app to be running at the baseURL.
  // It checks for the presence of the app title or a known element.
  try {
    await page.goto('/');
    // Check if the page title contains "Kiroshi" (case insensitive)
    await expect(page).toHaveTitle(/Kiroshi/i);
  } catch (error) {
    console.log('Sanity check failed, possibly due to app not running:', error);
    // We don't want to fail the build if the app isn't running in this context if we just want to fix the "no tests found" or "missing config" error.
    // However, for a real CI pipeline, we probably want it to fail if the app is down.
    // Given the CI logs showed connection failure, let's keep it simple for now.
    throw error;
  }
});
