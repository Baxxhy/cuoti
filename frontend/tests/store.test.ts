import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAppStore } from '../src/store/index.js'

describe('本地角色状态', () => {
  beforeEach(() => setActivePinia(createPinia()))
  it('默认进入学生视图', () => {
    expect(useAppStore().role).toBe('student')
  })
})
