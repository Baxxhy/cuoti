import { describe, expect, it, vi } from 'vitest'
import {
  choiceAnswer,
  editedStudentSteps,
  isMultipleChoice,
  normalizeOptions,
  questionRoute,
  questionTypeLabel,
} from '../src/utils/question.js'
import { waitForProcessingJob } from '../src/utils/processing.js'
import { errorMessage } from '../src/api/index.js'

describe('真实题目作答与识别恢复', () => {
  it('从错题列表恢复到真正未完成的步骤', () => {
    expect(questionRoute({ id: 'q1', status: 'awaiting_crop' })).toBe('/pages/crop/crop?id=q1')
    expect(questionRoute({ id: 'q1', status: 'processing', latest_job_id: 'job1' })).toBe(
      '/pages/ocr/ocr?id=q1&job=job1',
    )
    expect(questionRoute({ id: 'q1', status: 'partial', latest_job_id: 'job2' })).toBe(
      '/pages/ocr/ocr?id=q1&job=job2',
    )
    expect(questionRoute({ id: 'q1', status: 'ocr_draft' })).toBe('/pages/ocr/ocr?id=q1')
    expect(questionRoute({ id: 'q1', status: 'diagnosed' })).toBe('/pages/detail/detail?id=q1')
  })

  it('兼容题库 key、识别 label 和字符串选项，按题目顺序提交多选答案', () => {
    const options = [{ key: 'A', content: '甲' }, { label: 'B', text: '乙' }, '丙']
    expect(normalizeOptions(options)).toMatchObject([
      { label: 'A', text: '甲' },
      { label: 'B', text: '乙' },
      { label: 'C', text: '丙' },
    ])
    expect(choiceAnswer(['C', 'A', 'C', 'Z'], options)).toBe('A、C')
    expect(choiceAnswer([], options)).toBe('')
    expect(normalizeOptions(null)).toEqual([])
    for (const type of ['multiple_choice', '多选题', '多项选择题'])
      expect(isMultipleChoice(type)).toBe(true)
    expect(isMultipleChoice('choice')).toBe(false)
  })

  it('按CMMU源题型区分单选与多选，并显示中文名称', () => {
    expect(isMultipleChoice('multiple-choice')).toBe(false)
    expect(isMultipleChoice('multiple-response')).toBe(true)
    expect(questionTypeLabel('multiple-choice')).toBe('单选题')
    expect(questionTypeLabel('multiple-response')).toBe('多选题')
    expect(questionTypeLabel('fill-in-the-blank')).toBe('填空题')
    expect(questionTypeLabel('证明题')).toBe('证明题')
  })

  it('编辑步骤后清除旧公式与原始识别内容，并过滤空步骤', () => {
    const original = [
      {
        text: 'x = 3',
        formula: 'x = 2',
        raw_text: 'x = 2',
        normalized_text: 'x = 2',
        source: 'qwen_crop',
      },
      { text: '', formula: '' },
    ]
    const result = editedStudentSteps(original)
    expect(result).toEqual([
      {
        text: 'x = 3',
        formula: 'x = 3',
        raw_text: 'x = 3',
        normalized_text: 'x = 3',
        source: 'user',
      },
    ])
    expect(original[0].formula).toBe('x = 2')
    expect(editedStudentSteps([{ text: '改为利用相似三角形', formula: 'x=2' }])[0].formula).toBe('')
    expect(editedStudentSteps([{ formula: 'a = b' }])[0].text).toBe('a = b')
  })

  it('重新识别只有在任务完成后才允许加载题目', async () => {
    const getJob = vi
      .fn()
      .mockResolvedValueOnce({ status: 'processing', progress: 45 })
      .mockResolvedValueOnce({ status: 'completed', progress: 100 })
    const onProgress = vi.fn()
    const wait = vi.fn().mockResolvedValue(undefined)
    expect(await waitForProcessingJob('job-1', { getJob, onProgress, wait })).toBe(true)
    expect(getJob).toHaveBeenCalledTimes(2)
    expect(getJob).toHaveBeenCalledWith('job-1')
    expect(onProgress).toHaveBeenLastCalledWith({ status: 'completed', progress: 100 })
  })

  it('识别失败可启动新任务，等待超时保留原任务供再次查询', async () => {
    await expect(
      waitForProcessingJob('failed', { getJob: async () => ({ status: 'failed' }) }),
    ).rejects.toMatchObject({ jobFailed: true })
    const now = vi.fn().mockReturnValueOnce(0).mockReturnValue(10)
    await expect(
      waitForProcessingJob('slow', {
        getJob: async () => ({ status: 'processing' }),
        timeoutMs: 5,
        now,
      }),
    ).rejects.toThrow('识别仍在处理中')
  })

  it('题目归档导致识别取消时立即结束等待，不继续轮询', async () => {
    const wait = vi.fn().mockRejectedValue(new Error('cancelled job must not wait'))
    await expect(
      waitForProcessingJob('cancelled', {
        getJob: async () => ({ status: 'cancelled', error: '题目已归档，识别任务已取消' }),
        wait,
      }),
    ).rejects.toMatchObject({ jobCancelled: true, message: '题目已归档，识别任务已取消' })
    expect(wait).not.toHaveBeenCalled()
  })

  it('离开页面后不再交付迟到的识别结果', async () => {
    let active = true
    const onProgress = vi.fn()
    const getJob = async () => {
      active = false
      return { status: 'completed' }
    }
    expect(
      await waitForProcessingJob('job-1', { getJob, onProgress, isActive: () => active }),
    ).toBe(false)
    expect(onProgress).not.toHaveBeenCalled()
  })

  it('验证错误展示可读信息，不将对象传入提示框', () => {
    expect(errorMessage({ detail: [{ msg: '答案不能为空' }, { msg: '请选择题型' }] })).toBe(
      '答案不能为空；请选择题型',
    )
    expect(errorMessage({ detail: '当前密码错误' })).toBe('当前密码错误')
    expect(errorMessage({ detail: { internal: 'data' } })).toBe('请求没有成功')
  })
})
