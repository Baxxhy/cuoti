import { defineConfig, devices } from '@playwright/test'
import { existsSync } from 'node:fs'
import path from 'node:path'

const frontendPort = process.env.ZHIWEI_FRONTEND_PORT || '5173'
const backendPort = process.env.ZHIWEI_BACKEND_PORT || '8000'
const frontendURL = process.env.ZHIWEI_FRONTEND_URL || `http://127.0.0.1:${frontendPort}`
const backendURL = process.env.ZHIWEI_API_URL || `http://127.0.0.1:${backendPort}/api/v1`
const bundledBrowser = path.resolve('.playwright-browsers/chromium-1234/chrome-linux64/chrome')
const executablePath =
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ||
  (existsSync(bundledBrowser) ? bundledBrowser : undefined)
const bundledLibraries = path.resolve('.playwright-libs/root/usr/lib/x86_64-linux-gnu')

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  use: {
    baseURL: frontendURL,
    ignoreHTTPSErrors: process.env.QA_PREVIEW_HTTPS === '1',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: {
      executablePath,
      args: ['--no-sandbox'],
      env: {
        ...process.env,
        LD_LIBRARY_PATH: [
          existsSync(bundledLibraries) ? bundledLibraries : '',
          process.env.LD_LIBRARY_PATH,
        ]
          .filter(Boolean)
          .join(path.delimiter),
      },
    },
  },
  webServer: [
    {
      command:
        process.env.ZHIWEI_BACKEND_KIND === 'cangjie'
          ? 'bash scripts/cangjie.sh run'
          : 'make backend',
      cwd: path.resolve('..'),
      url: `${backendURL}/system/health`,
      reuseExistingServer: true,
      timeout: 120_000,
      env: { CI: '1' },
    },
    {
      command: `pnpm run dev:h5 --host 127.0.0.1 --port ${frontendPort} --strictPort`,
      url: frontendURL,
      ignoreHTTPSErrors: process.env.QA_PREVIEW_HTTPS === '1',
      reuseExistingServer: true,
      timeout: 120_000,
      env: { CI: '1', ZHIWEI_BACKEND_URL: new URL(backendURL).origin },
    },
  ],
  projects: [{ name: 'mobile-chromium', use: { ...devices['Pixel 7'] } }],
  reporter: 'line',
})
