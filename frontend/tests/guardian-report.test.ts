import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Report from '../src/pages/guardian/report.vue'
const fake = vi.hoisted(() => ({
  getData: vi.fn(),
  hooks: {} as Record<string, (...args: any[]) => any>,
}))
vi.mock('@dcloudio/uni-app', () => ({
  onLoad: (fn: any) => (fake.hooks.load = fn),
  onShow: (fn: any) => (fake.hooks.show = fn),
  onHide: (fn: any) => (fake.hooks.hide = fn),
  onUnload: (fn: any) => (fake.hooks.unload = fn),
}))
vi.mock('../src/api/index.js', () => ({ getData: fake.getData }))
vi.mock('../src/utils/navigation.js', () => ({ go: vi.fn() }))
let wrapper: ReturnType<typeof mount> | undefined
function make() {
  wrapper = mount(Report, {
    global: {
      stubs: {
        'app-header': true,
        'state-panel': { props: ['message'], template: '<div class="error">{{message}}</div>' },
        'student-report': {
          props: ['data'],
          template: '<div class="report">{{data.student.name}}</div>',
        },
      },
    },
  })
  fake.hooks.load({ id: 'child' })
  return wrapper
}
beforeEach(() => {
  fake.getData.mockReset()
})
afterEach(() => {
  wrapper?.unmount()
})
it('hiding clears report and ignores a late read before revalidating on show', async () => {
  let resolve: (value: any) => void = () => {}
  fake.getData.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done
    }),
  )
  const page = make()
  fake.hooks.show()
  fake.hooks.hide()
  resolve({ student: { name: 'old private child' } })
  await flushPromises()
  expect(page.find('.report').exists()).toBe(false)
  fake.getData.mockRejectedValueOnce(Object.assign(new Error('denied'), { statusCode: 403 }))
  fake.hooks.show()
  await flushPromises()
  expect(page.text()).toContain('当前已无权查看这份报告')
  expect(page.text()).not.toContain('old private child')
  expect(fake.getData).toHaveBeenCalledTimes(2)
})
it('refresh drops previously loaded data if authorization has been revoked', async () => {
  fake.getData.mockResolvedValueOnce({ student: { name: 'visible child' } })
  const page = make()
  fake.hooks.show()
  await flushPromises()
  expect(page.find('.report').text()).toBe('visible child')
  fake.getData.mockRejectedValueOnce(Object.assign(new Error('denied'), { statusCode: 403 }))
  await page.find('button').trigger('click')
  await flushPromises()
  expect(page.find('.report').exists()).toBe(false)
  expect(page.text()).toContain('返回家长中心')
})
it('out-of-order reads cannot replace a newer permission denial', async () => {
  let resolve: (value: any) => void = () => {}
  fake.getData.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done
    }),
  )
  const page = make()
  fake.hooks.show()
  fake.getData.mockRejectedValueOnce(Object.assign(new Error('denied'), { statusCode: 403 }))
  fake.hooks.show()
  await flushPromises()
  resolve({ student: { name: 'stale child' } })
  await flushPromises()
  expect(page.find('.report').exists()).toBe(false)
  expect(page.text()).toContain('当前已无权查看这份报告')
})
