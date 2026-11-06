export async function waitForProcessingJob(
  jobId,
  {
    getJob,
    onProgress = () => {},
    isActive = () => true,
    wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
    timeoutMs = 180000,
    now = Date.now,
  },
) {
  const started = now()
  while (isActive()) {
    const job = await getJob(jobId)
    if (!isActive()) return false
    onProgress(job)
    if (job.status === 'completed') return true
    if (job.status === 'failed')
      throw Object.assign(new Error('识别未完成，请重新识别或调整图片范围。'), { jobFailed: true })
    if (job.status === 'cancelled')
      throw Object.assign(new Error(job.error || '识别任务已取消，请返回错题本。'), {
        jobCancelled: true,
      })
    if (now() - started >= timeoutMs) throw new Error('识别仍在处理中，可稍后点击重试查看结果。')
    await wait(900)
  }
  return false
}
