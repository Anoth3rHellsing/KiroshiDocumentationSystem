
import { test, expect } from '@playwright/test';

test('app should load', async ({ page }) => {
  await page.goto('/');
  // Check if title contains Kiroshi or Streamlit default
  await expect(page).toHaveTitle(/Kiroshi|Streamlit/);
});
