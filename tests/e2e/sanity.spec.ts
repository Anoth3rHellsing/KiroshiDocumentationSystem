import { test, expect } from '@playwright/test';

test('App load test', async ({ page }) => {
  // Go to the local Streamlit server port, which matches CI
  await page.goto('http://localhost:8501');

  // Verify that the Streamlit app loads properly
  const appContainer = page.locator('.stApp');
  await expect(appContainer).toBeVisible({ timeout: 15000 });
});
