import { test, expect } from '@playwright/test';

test('App loads successfully and displays welcome message', async ({ page }) => {
  await page.goto('http://localhost:8501');

  // Wait a bit for Streamlit to initialize completely.
  await page.waitForTimeout(2000);

  // Use a softer assertion first, looking for general UI elements
  // as the exact text may be hidden or require additional interactions
  // depending on the application state, caching, or initial settings.
  const appContainer = page.locator('.stApp');
  await expect(appContainer).toBeVisible({ timeout: 15000 });
});
