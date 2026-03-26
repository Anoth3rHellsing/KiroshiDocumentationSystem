import { test, expect } from '@playwright/test';

test('App load sanity check', async ({ page }) => {
  // Navigate to the app on the CI port
  await page.goto('http://localhost:8501');

  // Wait for the Streamlit app container to be visible
  await expect(page.locator('.stApp')).toBeVisible();
});
