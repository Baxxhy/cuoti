import { afterEach, expect, it, vi } from 'vitest'
import { downloadExportFile, openExportFile } from '../src/utils/export-file.js'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})
function popup() {
  return {
    opener: {},
    document: { title: '', body: { textContent: '' } },
    location: { replace: vi.fn() },
    close: vi.fn(),
  }
}
it('点击时先打开窗口，链接更新完成后才导航并解除 opener', async () => {
  const tab = popup(),
    open = vi.spyOn(window, 'open').mockReturnValue(tab as any)
  let resolve: (url: string) => void = () => {}
  const getUrl = vi.fn(
    () =>
      new Promise<string>((r) => {
        resolve = r
      }),
  )
  const pending = openExportFile(getUrl)
  expect(open).toHaveBeenCalledWith('about:blank', '_blank')
  expect(tab.opener).toBeNull()
  expect(tab.document.body.textContent).toBe('正在打开文件…')
  expect(tab.location.replace).not.toHaveBeenCalled()
  resolve('/reports/new.pdf?expires=fresh')
  await pending
  expect(tab.location.replace).toHaveBeenCalledWith('/reports/new.pdf?expires=fresh')
})
it('更新链接失败时关闭等待窗口，返回错误供原页面重试', async () => {
  const tab = popup()
  vi.spyOn(window, 'open').mockReturnValue(tab as any)
  await expect(
    openExportFile(async () => {
      throw new Error('无法连接学习服务')
    }),
  ).rejects.toThrow('无法连接学习服务')
  expect(tab.close).toHaveBeenCalledOnce()
  expect(tab.location.replace).not.toHaveBeenCalled()
})
it('浏览器拒绝新窗口时给出可操作提示且不发出多余请求', async () => {
  vi.spyOn(window, 'open').mockReturnValue(null)
  const getUrl = vi.fn()
  await expect(openExportFile(getUrl)).rejects.toThrow('请允许浏览器打开新窗口')
  expect(getUrl).not.toHaveBeenCalled()
})
it('原生文件打开成功前保持等待，失败状态不能当作成功', async () => {
  const openDocument = vi.fn((options) => options.success({}))
  vi.stubGlobal('uni', {
    downloadFile: vi.fn((options) =>
      options.success({ statusCode: 200, tempFilePath: 'downloaded.pdf' }),
    ),
    openDocument,
  })
  await downloadExportFile(async () => '/reports/fresh.pdf')
  expect(openDocument).toHaveBeenCalledWith(
    expect.objectContaining({ filePath: 'downloaded.pdf', showMenu: true }),
  )
  vi.stubGlobal('uni', {
    downloadFile: vi.fn((options) => options.success({ statusCode: 403 })),
    openDocument,
  })
  await expect(downloadExportFile(async () => '/reports/expired.pdf')).rejects.toThrow(
    '暂时无法下载',
  )
  expect(openDocument).toHaveBeenCalledTimes(1)
})
