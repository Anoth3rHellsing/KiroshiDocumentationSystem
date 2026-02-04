import { test, expect } from '@playwright/test';

test('sanity check - app loads', async ({ page }) => {
  await page.goto('/');

  // Wait for the title to be set (Streamlit sets it dynamically)
  await expect(page).toHaveTitle(/Kiroshi|Case Documentation/i);

  // Wait for the main app container to be visible
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible();
});
