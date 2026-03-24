import { test, expect } from '@playwright/test';

test('App load sanity check', async ({ page }) => {
    // Navigate to the app
    await page.goto('http://127.0.0.1:8501');

    // Verification of app load checks for the 'Saved Cases' tab rather than the 'Add Case' button
    // Playwright selectors in tests/e2e/sanity.spec.ts use .first() on common elements like tabs to avoid strict mode violations.
    const savedCasesTab = page.getByRole('tab', { name: 'Saved Cases' }).first();
    await expect(savedCasesTab).toBeVisible({ timeout: 15000 });
});
