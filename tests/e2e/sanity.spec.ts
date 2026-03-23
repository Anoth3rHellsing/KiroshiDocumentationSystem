import { test, expect } from '@playwright/test';

test('sanity', async ({ page }) => {
  await page.goto('http://localhost:8501');
  await expect(page.getByRole('tab', { name: 'Saved Cases' }).first()).toBeVisible();
});
