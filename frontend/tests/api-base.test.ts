import { describe, expect, it } from 'vitest'
import { normalizeApiBase, resolveApiBase } from '../src/utils/api-base.js'

describe('手机服务连接配置', () => {
  it('正式包使用构建地址并忽略历史模拟器缓存', () => {
    expect(
      resolveApiBase({
        native: true,
        configured: 'https://school.example/api/v1/',
        stored: 'http://10.0.2.2:8000/api/v1',
      }),
    ).toBe('https://school.example/api/v1')
    expect(() => resolveApiBase({ native: true })).toThrow('完整')
    expect(() => resolveApiBase({ native: true, configured: 'http://school.example' })).toThrow(
      'HTTPS',
    )
  })
  it('H5保留同源代理，本地App连接仓颉端口', () => {
    expect(resolveApiBase()).toBe('/api/v1')
    expect(resolveApiBase({ native: true, development: true })).toBe('http://10.0.2.2:8002/api/v1')
    expect(
      resolveApiBase({ native: true, development: true, stored: 'http://192.168.1.2:8002' }),
    ).toBe('http://192.168.1.2:8002/api/v1')
  })
  it.each([
    'javascript:alert(1)',
    'https://user:secret@school.example/api/v1',
    'https://school.example/api/v1?token=abc',
    'https://school.example/api/v1#x',
    'https://school.example/other',
    '//school.example/api/v1',
  ])('拒绝含歧义或凭据的地址 %s', (value) => {
    expect(() => normalizeApiBase(value)).toThrow()
  })
})
