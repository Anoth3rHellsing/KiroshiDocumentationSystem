import { test, expect } from '@playwright/test';

test('App sanity check', async ({ page }) => {
  // Navigate to the app (baseURL is set in playwright.config.ts)
  await page.goto('/');

  // Expect the page to have the correct title or some key element
  // Since Streamlit title might load late, we wait for the app container
  const appContainer = page.locator('.stApp');
  await expect(appContainer).toBeVisible({ timeout: 30000 });
});
