import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { mount } from '@vue/test-utils'
import { browser, parsePage, getBrowserPages, currentUrl } from '../src/platform/browser.js'
import { WebInput, WebPicker, WebImage, WebMovable, WebCheckboxGroup, WebCheckbox } from '../src/platform/components.js'
import routes from '../src/routes.json'
import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'

beforeEach(()=>{localStorage.clear();vi.spyOn(window,'scrollTo').mockImplementation(()=>{})})
afterEach(()=>{vi.restoreAllMocks()})
describe('Web runtime preserves original page contracts',()=>{
 it('keeps all 36 original routes and real Vue pages',()=>{
  const original=JSON.parse(readFileSync(path.resolve('../reference/frontend/src/pages.json'))).pages.map(x=>x.path)
  expect(routes).toEqual(original)
  for(const route of routes)expect(readFileSync(path.resolve('src',route+'.vue'),'utf8')).toContain('<template>')
 })
 it('does not depend on a uni-app runtime or compiler',()=>{
  const pkg=JSON.parse(readFileSync(path.resolve('package.json')))
  expect(Object.keys({...pkg.dependencies,...pkg.devDependencies}).some(x=>x.startsWith('@dcloudio/'))).toBe(false)
  const config=readFileSync(path.resolve('vite.config.js'),'utf8')
  expect(config).toContain('@vitejs/plugin-vue')
  const files=folder=>readdirSync(folder,{withFileTypes:true}).flatMap(e=>e.isDirectory()?files(path.join(folder,e.name)):[path.join(folder,e.name)])
  for(const file of files(path.resolve('src')).filter(f=>/\.(js|vue|ts)$/.test(f))){
   const text=readFileSync(file,'utf8')
   expect(text).not.toMatch(/from\s+['"]@dcloudio/)
   expect(text).not.toMatch(/\buni\s*\./)
  }
 })
 it('preserves typed storage values and draft enumeration',()=>{
  browser.setStorageSync('draft',{steps:['2x=8'],helped:false})
  expect(browser.getStorageSync('draft')).toEqual({steps:['2x=8'],helped:false})
  expect(browser.getStorageInfoSync().keys).toContain('draft')
  browser.removeStorageSync('draft');expect(browser.getStorageSync('draft')).toBe('')
 })
 it('preserves route query and replacement semantics',()=>{
  browser.reLaunch({url:'/pages/detail/detail?id=a%2Fb'})
  expect(getBrowserPages()[0].options.id).toBe('a/b')
  browser.navigateTo({url:'/pages/task/task?id=t1'})
  expect(getBrowserPages()).toHaveLength(2)
  browser.redirectTo({url:'/pages/ocr/ocr?id=q1'})
  expect(getBrowserPages()).toHaveLength(2)
  expect(currentUrl.value).toBe('/pages/ocr/ocr?id=q1')
  expect(parsePage('/pages/detail/detail?id=hello%20world').options.id).toBe('hello world')
 })
 it('converts native typing into the original detail.value event',async()=>{
  const wrapper=mount(WebInput,{props:{modelValue:'',maxlength:30}})
  await wrapper.find('input').setValue('两边减2')
  expect(wrapper.emitted('input')[0][0].detail.value).toBe('两边减2')
  expect(wrapper.emitted('update:modelValue')[0]).toEqual(['两边减2'])
  wrapper.unmount()
 })
 it('emits numeric picker indexes and date strings',async()=>{
  const picker=mount(WebPicker,{props:{range:['初一','初二'],value:0}})
  await picker.find('select').setValue('1')
  expect(picker.emitted('change')[0][0].detail.value).toBe(1)
  picker.unmount()
  const date=mount(WebPicker,{props:{mode:'date',value:'2026-11-07'}})
  await date.find('input').setValue('2026-11-08')
  expect(date.emitted('change')[0][0].detail.value).toBe('2026-11-08')
  date.unmount()
 })
 it('reports image dimensions used by the existing crop algorithm',async()=>{
  const image=mount(WebImage,{props:{src:'/test.png'}})
  Object.defineProperties(image.element,{naturalWidth:{value:600},naturalHeight:{value:400}})
  await image.trigger('load')
  expect(image.emitted('load')[0][0].detail).toEqual({width:600,height:400})
  image.unmount()
 })
 it('keeps HTTP errors visible to original API handling',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({detail:'请先登录'}),{status:401})))
  const response=await new Promise((resolve,reject)=>browser.request({url:'/api/v1/auth/me',success:resolve,fail:reject}))
  expect(response.statusCode).toBe(401)
  expect(response.data.detail).toBe('请先登录')
  vi.unstubAllGlobals()
 })
})


it('keeps already selected checkbox values when adding another choice',async()=>{
 const wrapper=mount(WebCheckboxGroup,{slots:{default:()=>[h(WebCheckbox,{value:'a',checked:true}),h(WebCheckbox,{value:'b',checked:false})]}})
 await wrapper.findAll('input')[1].setValue(true)
 expect(wrapper.emitted('change')[0][0].detail.value.sort()).toEqual(['a','b'])
 wrapper.unmount()
})
