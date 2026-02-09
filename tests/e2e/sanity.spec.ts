
import { test, expect } from '@playwright/test';

test('App loads and title is correct', async ({ page }) => {
  await page.goto('/');

  // Wait for the main app container to ensure it's loaded
  await page.waitForSelector('.stApp', { timeout: 30000 });

  // Check for the title
  await expect(page).toHaveTitle(/Kiroshi/);
});
