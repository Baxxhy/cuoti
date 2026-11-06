import {defineConfig,devices} from '@playwright/test'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(root,'.runtime/playwright-browsers')
export default defineConfig({
 testDir:'./e2e',workers:1,timeout:60000,
 outputDir:process.env.SCZX_E2E_OUTPUT||path.join(root,'.runtime/e2e'),
 use:{baseURL:process.env.SCZX_WEB_URL||'http://127.0.0.1:5176',trace:'retain-on-failure',screenshot:'only-on-failure',launchOptions:{args:['--no-sandbox']}},
 projects:[{name:'mobile-chromium',use:{...devices['Pixel 7']}}],reporter:'line'
})
