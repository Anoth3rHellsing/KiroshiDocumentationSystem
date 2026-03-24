import { FullConfig } from '@playwright/test';
export default async function globalSetup(config: FullConfig) {
    console.log("Global setup running...");
}
