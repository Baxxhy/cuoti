// Kept platform independent so release and local-device rules share one validator.
export function normalizeApiBase(value, { allowHttp = false, allowRelative = false } = {}) {
  const raw = String(value || '')
    .trim()
    .replace(/\/+$/, '')
  if (allowRelative && raw === '/api/v1') return raw
  let parsed
  try {
    parsed = new URL(raw)
  } catch {
    throw new Error('请配置完整的学习服务地址')
  }
  if (parsed.protocol !== 'https:' && !(allowHttp && parsed.protocol === 'http:')) {
    throw new Error('正式学习服务必须使用 HTTPS')
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error('服务地址不能包含账号、参数或锚点')
  }
  const path = parsed.pathname.replace(/\/+$/, '')
  if (path && !path.endsWith('/api/v1')) {
    throw new Error('学习服务地址应以 /api/v1 结尾')
  }
  return `${parsed.origin}${path || '/api/v1'}`
}

export function resolveApiBase({
  native = false,
  development = false,
  configured = '',
  stored = '',
} = {}) {
  // A cached development address must never override the server selected for release.
  const value =
    (development && stored) ||
    configured ||
    (native ? (development ? 'http://10.0.2.2:8002/api/v1' : '') : '/api/v1')
  return normalizeApiBase(value, { allowHttp: development, allowRelative: !native })
}
