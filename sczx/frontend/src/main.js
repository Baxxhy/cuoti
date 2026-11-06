import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import * as controls from './platform/components.js'
import 'katex/dist/katex.min.css'
const app=createApp(App)
app.use(createPinia())
Object.entries(controls).forEach(([name,component])=>app.component(name,component))
const components=import.meta.glob('./components/*/*.vue',{eager:true,import:'default'})
Object.entries(components).forEach(([path,component])=>app.component(path.split('/').at(-2),component))
app.mount('#app')
