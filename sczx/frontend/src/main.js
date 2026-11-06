import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import * as controls from './platform/components.js'
import 'katex/dist/katex.min.css'
// Original H5 uses 32rpx per rem and a 375px base above 960px.
function updateRelativeUnits(){
 const apple=/^Apple/.test(navigator.vendor)&&typeof window.orientation==='number'
 const landscape=apple&&Math.abs(window.orientation)===90
 const screenWidth=apple?Math[landscape?'max':'min'](screen.width,screen.height):screen.width
 const width=Math.min(window.innerWidth,document.documentElement.clientWidth,screenWidth)||screenWidth
 document.documentElement.style.fontSize=((width<=960?width:375)/23.4375)+'px'
}
updateRelativeUnits()
window.addEventListener('resize',updateRelativeUnits)
window.addEventListener('load',updateRelativeUnits)
const app=createApp(App)
app.use(createPinia())
Object.entries(controls).forEach(([name,component])=>app.component(name,component))
const components=import.meta.glob('./components/*/*.vue',{eager:true,import:'default'})
Object.entries(components).forEach(([path,component])=>app.component(path.split('/').at(-2),component))
app.mount('#app')
