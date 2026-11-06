import { mediaUrl } from '@/api/index.js'

export async function downloadExportFile(getUrl) {
  const url = mediaUrl(await getUrl())
  await new Promise((resolve, reject) => {
    uni.downloadFile({
      url,
      success(response) {
        if (response.statusCode !== 200) {
          reject(new Error('文件暂时无法下载，请稍后重试'))
          return
        }
        uni.openDocument({
          filePath: response.tempFilePath,
          showMenu: true,
          success: resolve,
          fail: () => reject(new Error('此设备暂时无法打开该文件')),
        })
      },
      fail: () => reject(new Error('文件下载失败，请重试')),
    })
  })
}

export async function openExportFile(getUrl) {
  // #ifdef H5
  // Open during the click gesture so browsers allow the new window.
  const popup = window.open('about:blank', '_blank')
  if (!popup) throw new Error('请允许浏览器打开新窗口后重试')
  popup.opener = null
  popup.document.title = '正在打开文件'
  popup.document.body.textContent = '正在打开文件…'
  try {
    const url = await getUrl()
    popup.location.replace(mediaUrl(url))
  } catch (error) {
    popup.close()
    throw error
  }
  return
  // #endif
  // #ifndef H5
  await downloadExportFile(getUrl)
  // #endif
}
