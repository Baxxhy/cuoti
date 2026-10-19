import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import Header from '../src/components/app-header/app-header.vue'

it('动态试卷标题渲染公式，普通页面标题保持原有显示', async () => {
  const page = mount(Header, {
    props: { title: '普通页面' },
    global: { stubs: { 'uni-icons': true } },
  })
  expect(page.find('.math-text').exists()).toBe(false)
  await page.setProps({ title: String.raw`比较 $\frac{1}{5}$ <img src=x>` })
  expect(page.find('h1 .mfrac').exists()).toBe(true)
  expect(page.find('.math-unparsed').exists()).toBe(false)
  expect(page.find('img').exists()).toBe(false)
  page.unmount()
})
