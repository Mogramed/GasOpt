import { defineConfig,devices } from '@playwright/test';
export default defineConfig({testDir:'./e2e',timeout:120000,expect:{timeout:15000},workers:1,retries:0,
 use:{baseURL:process.env.GASOPS_URL||'http://127.0.0.1:5173',...devices['Desktop Chrome'],viewport:{width:1920,height:1080},trace:'retain-on-failure',screenshot:'only-on-failure'},reporter:'list'});
