import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // Just a placeholder test to ensure runner works
  await page.goto('/');
  // Basic check - title might vary so we check for something generic or just pass
  // The app title is likely "Kiroshi..."
  const title = await page.title();
  console.log('Page title:', title);
  // Expect title to contain Kiroshi (case insensitive)
  expect(title).toMatch(/Kiroshi/i);
});
