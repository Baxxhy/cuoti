export function go(url, options = {}) {
  if (!url) return
  if (options.replace) return uni.redirectTo({ url })
  if (options.relaunch) return uni.reLaunch({ url })
  return uni.navigateTo({ url })
}

// A task may have been opened from its question or from history. Reuse the
// matching question when it exists so repeated learning never grows the stack.
export function returnToQuestion(questionId) {
  const pages = getCurrentPages()
  const target = String(questionId || '')
  let index = -1
  for (let i = pages.length - 1; i >= 0; i--) {
    const page = pages[i]
    if ((page.route || '').replace(/^\//, '') !== 'pages/detail/detail') continue
    const options = page.options || page.$page?.options || {}
    let matches = String(options.id || '') === target
    if (!matches) {
      try {
        matches =
          new URL(page.$page?.fullPath || '', 'https://local.invalid').searchParams.get('id') ===
          target
      } catch {
        /* Keep the safe fallback. */
      }
    }
    if (matches) {
      index = i
      break
    }
  }
  if (index >= 0 && index < pages.length - 1)
    return uni.navigateBack({ delta: pages.length - 1 - index })
  return uni.reLaunch({ url: `/pages/detail/detail?id=${encodeURIComponent(target)}` })
}

export function back(fallback) {
  const pages = getCurrentPages()
  const route = (pages[pages.length - 1]?.route || '').replace(/^\//, '')
  const parents = {
    'pages/detail/detail': '/pages/problem/list',
    'pages/manual/manual': '/pages/capture/capture',
    'pages/crop/crop': '/pages/capture/capture',
    'pages/preferences/preferences': '/pages/profile/profile',
    'pages/help/help': '/pages/profile/profile',
    'pages/bank/bank': '/pages/learning/learning',
    'pages/practice/practice': '/pages/learning/learning',
    'pages/analysis/analysis': '/pages/learning/learning',
    'pages/framework/framework': '/pages/learning/learning',
    'pages/review-search/review-search': '/pages/review/review',
    'pages/error-map/error-map': '/pages/learning/learning',
    'pages/task/task': '/pages/learning/learning',
    'pages/paper/paper-center': '/pages/learning/learning',
  }
  const home =
    parents[route] ||
    (route.startsWith('pages/admin/') || route.startsWith('pages/system/')
      ? '/pages/admin/workbench'
      : route === 'pages/register/register' || route === 'pages/forgot/forgot'
        ? '/pages/login/login'
        : '/pages/index/index')
  const returnToParent = () => uni.reLaunch({ url: fallback || home })
  if (pages.length > 1) uni.navigateBack({ fail: returnToParent })
  else returnToParent()
}

// Reuse an existing root when possible; cap stack growth when changing sections.
export function switchSection(url) {
  const pages = getCurrentPages()
  const route = url.replace(/^\//, '')
  const current = pages[pages.length - 1]
  if (current?.route === route) return
  const index = pages.findIndex((page) => page.route === route)
  if (index >= 0) return uni.navigateBack({ delta: pages.length - 1 - index })
  return uni.redirectTo({ url })
}
