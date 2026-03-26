import { test, expect } from '@playwright/test';

test('Sanity check - Kiroshi App Loads', async ({ page }) => {
  await page.goto('/');
  await page.waitForTimeout(2000); // Give Streamlit some time to render
  const appContainer = page.locator('.stApp');
  await expect(appContainer).toBeVisible({ timeout: 15000 });
});
