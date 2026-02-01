import { test, expect } from '@playwright/test';

test('App loads successfully', async ({ page }) => {
  await page.goto('/');
  // Basic check for Streamlit app container
  await expect(page.locator('.stApp')).toBeVisible();
});
