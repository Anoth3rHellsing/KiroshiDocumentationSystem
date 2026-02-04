import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  await page.goto('/');
  // Allow time for streamlit to load
  await page.waitForLoadState('networkidle');
  // Check if main app container is present
  await expect(page.locator('.stApp')).toBeVisible();
});
