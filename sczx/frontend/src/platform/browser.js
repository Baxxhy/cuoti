import { shallowRef } from 'vue'

function locationUrl() {
  return window.location.hash.slice(1) || '/pages/index/index'
}
export function parsePage(url) {
  const parsed = new URL(url, 'https://sczx.local')
  return { route: parsed.pathname.replace(/^\//, ''), options: Object.fromEntries(parsed.searchParams), $page: { fullPath: parsed.pathname + parsed.search } }
}
export const currentUrl = shallowRef(locationUrl())
let pageSequence=0
function pageEntry(url){return {...parsePage(url),key:'page-'+Date.now()+'-'+(++pageSequence)}}
let pages = (window.history.state?.sczxPages || [pageEntry(currentUrl.value)]).map(page=>page.key?page:{...page,key:'page-'+Date.now()+'-'+(++pageSequence)})
export const pageStack=shallowRef(pages)
window.history.replaceState({...window.history.state,sczxPages:pages},'')
const scrollPositions=new Map()
function rememberScroll(){if(pages.length)scrollPositions.set(pages.at(-1).key,window.scrollY||0)}
function publishPages(){pageStack.value=pages}
export const getBrowserPages = () => pages.map(p => ({ ...p, options: { ...p.options } }))
function navigate(options, replace = false, reset = false) {
  try {
    const url = String(options.url || '')
    if (!url.startsWith('/pages/')) throw new Error('页面地址不正确')
    rememberScroll()
    const page = pageEntry(url)
    pages = reset ? [page] : replace ? [...pages.slice(0, -1), page] : [...pages, page]
    window.history[replace || reset ? 'replaceState' : 'pushState']({ sczxPages: pages }, '', '#' + page.$page.fullPath)
    publishPages()
    currentUrl.value = page.$page.fullPath
    window.scrollTo?.(0, 0)
    options.success?.({})
    options.complete?.({})
  } catch (error) { options.fail?.(error); options.complete?.(error) }
}
window.addEventListener('popstate', () => {
  rememberScroll()
  pages = window.history.state?.sczxPages || [pageEntry(locationUrl())]
  publishPages()
  currentUrl.value = locationUrl()
  requestAnimationFrame(()=>window.scrollTo?.(0,scrollPositions.get(pages.at(-1).key)||0))
})
window.addEventListener('hashchange', () => {
  currentUrl.value = locationUrl()
  if (pages.at(-1)?.$page.fullPath !== currentUrl.value){pages = [pageEntry(currentUrl.value)];publishPages()}
})
export const notice = shallowRef(null)
let noticeTimer
function result(options, value) { options.success?.(value); options.complete?.(value); return value }
function failed(options, error) { options.fail?.(error); options.complete?.(error) }
export const imagePreviewState = shallowRef(null)
export const modalState = shallowRef(null)
export const actionSheetState = shallowRef(null)
function openPopup(state, options, defaults) {
  const callbacks = ['success','fail','complete'].some(key => typeof options[key] === 'function')
  let resolve, reject
  const promise = callbacks ? undefined : new Promise((ok, no) => { resolve=ok; reject=no })
  state.value = {...defaults,...options,_resolve:resolve,_reject:reject}
  return promise
}
export function closeModal(confirm, content='') {
  const options=modalState.value
  if(!options)return
  modalState.value=null
  const value={confirm,cancel:!confirm,errMsg:'showModal:ok'}
  if(confirm&&options.editable)value.content=content
  result(options,value);options._resolve?.(value)
}
export function closeActionSheet(index=-1) {
  const options=actionSheetState.value
  if(!options)return
  actionSheetState.value=null
  if(index>=0&&index<options.itemList.length){
    const value={tapIndex:index,errMsg:'showActionSheet:ok'}
    result(options,value);options._resolve?.(value)
  }else{
    const error={errMsg:'showActionSheet:fail cancel'}
    failed(options,error);options._reject?.(error)
  }
}
const files = new Map()

export const browser = {
  getStorageSync(key) { try { const item = localStorage.getItem(key); return item === null ? '' : JSON.parse(item) } catch { return '' } },
  setStorageSync(key, value) { localStorage.setItem(key, JSON.stringify(value)) },
  removeStorageSync(key) { localStorage.removeItem(key) },
  getStorageInfoSync() { return { keys: Object.keys(localStorage) } },
  navigateTo: o => navigate(o), redirectTo: o => navigate(o, true), reLaunch: o => navigate(o, true, true),
  navigateBack(o = {}) {
    const delta = Math.max(1, Number(o.delta) || 1)
    if (pages.length <= delta) { failed(o, new Error('没有上一页')); return }
    window.history.go(-delta)
  },
  showToast(o) {
    notice.value = {title:String(o.title || ''),icon:o.icon||'success'}
    clearTimeout(noticeTimer)
    noticeTimer = setTimeout(() => { notice.value = null }, o.duration ?? 1500)
  },
  showModal(o) {
    return openPopup(modalState,o,{title:'',content:'',showCancel:true,cancelText:'取消',confirmText:'确定',cancelColor:'#000',confirmColor:'#007aff',editable:false,placeholderText:''})
  },
  showActionSheet(o) {
    return openPopup(actionSheetState,o,{itemColor:'#000',title:''})
  },
  request(o) {
    const controller = new AbortController()
    let reason=''
    const timer = setTimeout(() => {reason='timeout';controller.abort()}, o.timeout ?? 60000)
    let url = o.url
    const method = String(o.method || 'GET').toUpperCase()
    const headers = { ...o.header }
    let body
    if (method === 'GET' || method === 'HEAD') {
      if (o.data) { const q = new URLSearchParams(o.data); url += (url.includes('?') ? '&' : '?') + q }
    } else if (o.data !== undefined) {
      headers['Content-Type'] ??= 'application/json'
      body = JSON.stringify(o.data)
    }
    fetch(url, { method, headers, body, signal: controller.signal, credentials: 'same-origin' }).then(async response => {
      const text = await response.text()
      let data
      try { data = JSON.parse(text) } catch { data = text }
      result(o, { statusCode: response.status, data, header: Object.fromEntries(response.headers) })
    }).catch(error => failed(o, {errMsg:'request:fail '+(reason||error.message||'')})).finally(() => clearTimeout(timer))
    return { abort: () => {reason='abort';controller.abort()} }
  },
  uploadFile(o) {
    const xhr = new XMLHttpRequest()
    let progress
    xhr.open('POST', o.url)
    xhr.timeout = o.timeout ?? 60000
    Object.entries(o.header || {}).forEach(([k, v]) => xhr.setRequestHeader(k, v))
    xhr.upload.onprogress = e => { if (e.lengthComputable) progress?.({ progress: Math.round(e.loaded * 100 / e.total) }) }
    xhr.onload = () => result(o, { statusCode: xhr.status, data: xhr.responseText })
    xhr.onerror = () => failed(o, new Error('图片上传失败'))
    xhr.ontimeout = () => failed(o, new Error('图片上传超时'))
    xhr.onabort = () => failed(o, new Error('已取消上传'))
    ;(async () => {
      const blob = files.get(o.filePath) || await fetch(o.filePath).then(r => { if (!r.ok) throw new Error('读取图片失败'); return r.blob() })
      const form = new FormData()
      form.append(o.name || 'file', blob, blob.name || 'image.png')
      Object.entries(o.formData || {}).forEach(([k, v]) => form.append(k, String(v)))
      xhr.send(form)
    })().catch(error => failed(o, error))
    return { abort: () => xhr.abort(), onProgressUpdate: callback => { progress = callback } }
  },
  chooseImage(o) {
    const input = document.createElement('input')
    input.type = 'file'; input.accept = 'image/*'; input.multiple = (o.count || 1) > 1
    input.style.display = 'none'; document.body.appendChild(input)
    const cleanup = () => input.remove()
    input.onchange = () => {
      const selected = [...(input.files || [])].slice(0, o.count || 1)
      if (!selected.length) { failed(o, new Error('未选择图片')); cleanup(); return }
      const paths = selected.map(file => { const url = URL.createObjectURL(file); files.set(url, file); return url })
      result(o, { tempFilePaths: paths, tempFiles: selected.map((file, i) => ({ path: paths[i], size: file.size, name: file.name })) })
      cleanup()
    }
    input.oncancel = () => { failed(o, new Error('已取消')); cleanup() }
    input.click()
  },
  previewImage(o) {
    const urls=(o.urls||[]).map(url=>url?new URL(url,location.href).href:'')
    const requested=typeof o.current==='string'?urls.indexOf(new URL(o.current,location.href).href):o.current
    const index=Number.isInteger(requested)&&requested>=0&&requested<urls.length?requested:0
    imagePreviewState.value={urls,index}
    return result(o,{errMsg:'previewImage:ok'})
  },
  closePreviewImage(o={}) {
    if(!imagePreviewState.value)return failed(o,{errMsg:'closePreviewImage:fail'})
    imagePreviewState.value=null
    return result(o,{errMsg:'closePreviewImage:ok'})
  },
  setClipboardData(o) { navigator.clipboard.writeText(o.data).then(() => result(o, {})).catch(e => failed(o, e)) },
  getSystemInfoSync() { return { windowWidth: window.innerWidth, windowHeight: window.innerHeight, pixelRatio: window.devicePixelRatio || 1, platform: 'web' } },
  pageScrollTo(o) { window.scrollTo({ top: o.scrollTop || 0, behavior: o.duration === 0 ? 'instant' : 'smooth' }) },
  onWindowResize(callback) { window.addEventListener('resize', callback) },
  offWindowResize(callback) { window.removeEventListener('resize', callback) },
  createSelectorQuery() {
    let root = document, selector, callback
    return {
      in(instance) { root = instance?.$el || document; return this },
      select(value) { selector = value; return this },
      boundingClientRect(fn) { callback = fn; return this },
      exec() {
        const element = root.matches?.(selector) ? root : root.querySelector?.(selector)
        const rect = element?.getBoundingClientRect()
        callback?.(rect ? { width: rect.width, height: rect.height, left: rect.left, top: rect.top } : null)
      },
    }
  },
  createCanvasContext(id, instance) {
    const root = instance?.$el || document
    const canvas = root.id === id ? root : root.querySelector?.(`[id="${CSS.escape(id)}"]`) || document.getElementById(id)
    if (!canvas) throw new Error('绘图区未加载')
    const rect = canvas.getBoundingClientRect()
    if (rect.width && rect.height) { canvas.width = rect.width; canvas.height = rect.height }
    const context = canvas.getContext('2d')
    const aliases = { setFillStyle: 'fillStyle', setStrokeStyle: 'strokeStyle', setLineWidth: 'lineWidth', setLineCap: 'lineCap', setLineJoin: 'lineJoin', setTextAlign: 'textAlign', setTextBaseline: 'textBaseline', setGlobalAlpha: 'globalAlpha' }
    return new Proxy(context, { get(target, key) {
      if (aliases[key]) return value => { target[aliases[key]] = value }
      if (key === 'setFontSize') return value => { target.font = `${value}px sans-serif` }
      if (key === 'draw') return () => {}
      const value = target[key]; return typeof value === 'function' ? value.bind(target) : value
    } })
  },
  downloadFile(o) { fetch(o.url).then(async r => { const blob = await r.blob(); result(o, { statusCode: r.status, tempFilePath: URL.createObjectURL(blob) }) }).catch(e => failed(o, e)) },
  openDocument(o) { const w = window.open(o.filePath, '_blank', 'noopener'); if (w) result(o, {}); else failed(o, new Error('浏览器阻止打开文件')) },
}
