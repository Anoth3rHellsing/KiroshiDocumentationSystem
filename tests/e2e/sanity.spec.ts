import { test, expect } from '@playwright/test';

test('app loads and has correct title', async ({ page }) => {
  await page.goto('/');
  // Wait for title to contain Kiroshi (handling potential loading states)
  await expect(page).toHaveTitle(/Kiroshi/);

  // Basic verification that the app shell is present
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible();
});
