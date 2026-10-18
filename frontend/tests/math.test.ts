import { describe, expect, it } from 'vitest'
import { renderMathText } from '../src/utils/math'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

describe('数学公式文本渲染', () => {
  it('英文语法短语保留词间空格并继续转义普通文本', () => {
    const html = renderMathText('主句 $would tell$，假设 \\(If I were you\\)。<img src=x>')
    expect(html).toContain('would tell')
    expect(html).toContain('If I were you')
    expect(html).not.toContain('class="katex"')
    expect(html).toContain('&lt;img')
    expect(html).not.toContain('<img')
  })

  it('纯变量、函数和算式继续按数学渲染', () => {
    const html = renderMathText('$a b$ $sin x$ $x+1$ $\\cos x$')
    expect(html.match(/class="katex"/g)).toHaveLength(4)
  })
  it('渲染题干中的行内 TeX', () => {
    const html = renderMathText('已知 $A = \\{x \\mid x < a\\}$，求 $a \\ge 3$')
    expect(html).toContain('class="katex"')
    expect(html).toContain('≥')
    expect(html).not.toContain('$a \\ge 3$')
  })

  it('把根号命令显示为数学根号而不是原始 LaTex', () => {
    const html = renderMathText('满足不等式 $\\sqrt{x+1} < 2$ 的整数解')
    expect(html).toContain('class="mord sqrt"')
    expect(html).toContain('class="katex-html"')
  })

  it('兼容结构化输出误把 frac 的反斜杠变成控制符', () => {
    const html = renderMathText('判断：$\u000crac{1}{2}$ 属于有理数')
    expect(html).toContain('class="katex"')
    expect(html).not.toContain('\u000c')
  })

  it('支持块级 TeX 和圆括号分隔符', () => {
    const html = renderMathText('计算：\\(x+1\\)\n\\[x^2+1\\]')
    expect(html.match(/class="katex"/g)).toHaveLength(2)
    expect(html).toContain('katex-display')
  })

  it('转义公式之外的 HTML', () => {
    const html = renderMathText('<img src=x onerror=alert(1)> $x$')
    expect(html).toContain('&lt;img')
    expect(html).not.toContain('<img')
  })

  it('练习行内模式保留题句和短公式的连续阅读', () => {
    const html = renderMathText('如图，$$OA=OB$$，$$OC=OD$$。共有(\\quad)对。', true)
    expect(html.match(/class="katex"/g)).toHaveLength(2)
    expect(html).not.toContain('katex-display')
    expect(html).not.toContain('\\quad')
    expect(html).toContain('(　)对')
    expect(renderMathText('$$x^2+1$$')).toContain('katex-display')
  })

  it('教学流程的练习题干和选项都使用公式组件', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/pages/tutor/tutor.vue'), 'utf8')
    expect(source).toContain('<math-text class="activity-question" :text="activity.question" />')
    expect(source).toContain('<math-text class="option-label" :text="option.label" />')
  })

  it('确认题目页渲染题干、选项、答案和步骤中的公式', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/pages/ocr/ocr.vue'), 'utf8')
    expect(source).toContain(
      '<math-text v-else class="question-text" :text="form.question_text" />',
    )
    expect(source).toContain('<math-text :text="optionValue(option)" />')
    expect(source).toContain('<math-text v-else class="answer-text" :text="form.student_answer" />')
    expect(source).toContain(
      '<math-text v-else class="step-text" :text="step.formula || step.text" />',
    )
  })
})
