import { test, expect } from '@playwright/test';

test('Sanity check: App loads and title is correct', async ({ page }) => {
  await page.goto('/');
  // Streamlit apps often take a moment to load the actual title set by the script
  await expect(page).toHaveTitle(/Kiroshi/i, { timeout: 15000 });
});
