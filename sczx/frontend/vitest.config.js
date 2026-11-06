import { mergeConfig, defineConfig } from 'vitest/config'
import base from './vite.config.js'
export default mergeConfig(base,defineConfig({server:{hmr:false},test:{environment:'jsdom',globals:true,include:['tests/**/*.test.js']}}))
