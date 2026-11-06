import { browser } from '@/platform/browser.js'
import { normalizeApiBase, resolveApiBase } from '@/utils/api-base.js'

const development = import.meta.env.MODE !== 'production'
const configured = import.meta.env.VITE_API_BASE_URL || ''

export function getApiBase() {
  return resolveApiBase({ configured, development })
}

export function setApiBase(value) {
  if (!development) throw new Error('正式版本的服务地址由安装包配置')
  const normalized = normalizeApiBase(value, { allowHttp: true })
  browser.setStorageSync('minddimension_api_base', normalized)
  return normalized
}

export function mediaUrl(value) {
  if (!value || /^(https?:|blob:|data:|file:|wxfile:)/.test(value)) return value
  const base = getApiBase()
  return base.startsWith('https://') || base.startsWith('http://')
    ? `${base.replace(/\/api\/v1$/, '')}${value.startsWith('/') ? value : `/${value}`}`
    : value
}

function hydrateMedia(value) {
  if (Array.isArray(value)) return value.map(hydrateMedia)
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [
      key,
      typeof item === 'string' && (key === 'url' || key.endsWith('_url'))
        ? mediaUrl(item)
        : hydrateMedia(item),
    ]),
  )
}

function userHeaders(extra = {}) {
  const token = browser.getStorageSync('minddimension_access_token')
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...extra }
}

function toastError(message) {
  browser.showToast({ title: message || '暂时无法完成，请稍后重试', icon: 'none', duration: 2600 })
}

function handleUnauthorized(options) {
  browser.removeStorageSync('minddimension_access_token')
  if (!options.skipAuthRedirect) browser.reLaunch({ url: '/pages/login/login' })
}

function responseError(message, statusCode) {
  const error = new Error(typeof message === 'string' ? message : '请求没有成功')
  error.statusCode = statusCode
  return error
}

export function errorMessage(body, fallback = '请求没有成功') {
  const detail = body?.message || body?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail))
    return (
      detail
        .map((item) => item.msg || '')
        .filter(Boolean)
        .join('；') || fallback
    )
  return fallback
}

export function request(url, options = {}) {
  return new Promise((resolve, reject) => {
    browser.request({
      url: `${getApiBase()}${url}`,
      method: options.method || 'GET',
      data: options.data,
      timeout: options.timeout ?? 60000,
      header: userHeaders(options.headers),
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(hydrateMedia(response.data?.data ?? response.data))
          return
        }
        if (response.statusCode === 401) handleUnauthorized(options)
        const message = errorMessage(response.data)
        if (!options.silent) toastError(message)
        reject(responseError(message, response.statusCode))
      },
      fail(error) {
        if (!options.silent) toastError('无法连接学习服务')
        reject(error)
      },
    })
  })
}

export const getData = (url, options) => request(url, { ...options, method: 'GET' })
export const postData = (url, data, options) => request(url, { ...options, method: 'POST', data })
export const patchData = (url, data, options) => request(url, { ...options, method: 'PATCH', data })
export const deleteData = (url, options) => request(url, { ...options, method: 'DELETE' })

export function uploadFile(url, filePath, name = 'file', formData = {}, onProgress) {
  return new Promise((resolve, reject) => {
    const task = browser.uploadFile({
      url: `${getApiBase()}${url}`,
      filePath,
      name,
      formData,
      header: userHeaders(),
      success(response) {
        let body = response.data
        try {
          body = JSON.parse(body)
        } catch (_) {}
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(hydrateMedia(body?.data ?? body))
          return
        }
        if (response.statusCode === 401) handleUnauthorized({})
        const message = errorMessage(body, '上传没有成功')
        toastError(message)
        reject(responseError(message, response.statusCode))
      },
      fail(error) {
        toastError('图片上传失败')
        reject(error)
      },
    })
    task?.onProgressUpdate?.(({ progress }) => onProgress?.(Number(progress) || 0))
  })
}
