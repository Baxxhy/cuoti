import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DateTimeInput from '../src/components/date-time-input/date-time-input.vue'

it('日期与时间选择发送同一个真实时刻，显示本地时间且可以清除', async () => {
  const start = new Date(2026, 9, 15, 20, 30)
  const wrapper = mount(DateTimeInput, {
    props: { modelValue: start.toISOString(), clearable: true },
  })
  expect(wrapper.text()).toContain('2026-10-15')
  expect(wrapper.text()).toContain('20:30')
  const pickers = wrapper.findAll('picker')
  pickers[0].element.dispatchEvent(new CustomEvent('change', { detail: { value: '2026-10-16' } }))
  expect(wrapper.emitted('update:modelValue')![0]).toEqual([
    new Date(2026, 9, 16, 20, 30).toISOString(),
  ])
  pickers[1].element.dispatchEvent(new CustomEvent('change', { detail: { value: '09:15' } }))
  expect(wrapper.emitted('update:modelValue')![1]).toEqual([
    new Date(2026, 9, 15, 9, 15).toISOString(),
  ])
  await wrapper.find('button').trigger('click')
  expect(wrapper.emitted('update:modelValue')!.at(-1)).toEqual([''])
  wrapper.unmount()
})
