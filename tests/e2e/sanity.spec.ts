import { test, expect } from '@playwright/test';

test('sanity check: app loads and title is correct', async ({ page }) => {
  // The base URL is configured in playwright.config.ts (defaulting to http://127.0.0.1:8501)
  await page.goto('/');

  // Wait for the main app container to ensure Streamlit has loaded
  await page.waitForSelector('[data-testid="stAppViewContainer"]', { timeout: 15000 });

  // Verify the title contains "Kiroshi"
  await expect(page).toHaveTitle(/Kiroshi/);
});
