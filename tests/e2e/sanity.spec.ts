import { test, expect } from '@playwright/test';

test('App load sanity check', async ({ page }) => {
  // Wait for the Streamlit server to be ready before navigating
  const response = await page.request.get('http://localhost:8501/_stcore/health');
  expect(response.ok()).toBeTruthy();

  // Navigate to the app
  await page.goto('http://localhost:8501');

  // Verify the app container loads
  const stApp = page.locator('.stApp');
  await expect(stApp).toBeVisible({ timeout: 15000 });
});
