import { test, expect } from '@playwright/test';

test('sanity check - app loads', async ({ page }) => {
  // The base URL is configured in playwright.config.ts (default: http://127.0.0.1:8501)
  await page.goto('/');

  // Wait for the app to load (Streamlit usually puts "Streamlit" in title initially, then updates)
  // We check if the main container is present or title contains app name
  await expect(page).toHaveTitle(/Kiroshi/i);
});
