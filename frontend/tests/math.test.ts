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

  it('胆矾选项里的杂化、离子和电子排布公式不强制拆行', () => {
    for (const text of [
      '所有氧原子都采取$${sp^{3}}$$杂化',
      '$${Cu^{2+}}$$的价电子排布式为$${3d^{8}4s^{1}}$$',
    ]) {
      const html = renderMathText(text, true)
      expect(html).toContain('class="katex"')
      expect(html).not.toContain('katex-display')
      expect(html).not.toContain('katex-error')
    }
  })

  it('教学流程的练习题干和选项都使用公式组件', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/pages/tutor/tutor.vue'), 'utf8')
    expect(source).toContain(
      '<math-text class="activity-question" :text="activity.question" inline />',
    )
    expect(source).toContain('<math-text class="option-label" :text="option.label" inline />')
  })

  it('确认题目页渲染题干、选项、答案和步骤中的公式', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/pages/ocr/ocr.vue'), 'utf8')
    expect(source).toContain(
      '<math-text v-else class="question-text" :text="form.question_text" inline />',
    )
    expect(source).toContain('<math-text :text="optionValue(option)" inline />')
    expect(source).toContain('<math-text v-else class="answer-text" :text="form.student_answer" />')
    expect(source).toContain(
      '<math-text v-else class="step-text" :text="step.formula || step.text" />',
    )
  })
})

describe('公开题库公式兼容与原文保护', () => {
  it.each([
    String.raw`在 $$\triangleABC$$ 中，$$\angleA=60^{\circ}$$`,
    String.raw`$$\sinx+\cosx+\lnx+\omegax$$`,
    String.raw`$$\left(\triangleABC\right)$$`,
    '$${S}_{\\DeltaACE}=3c{m}^{2}$$',
    String.raw`$$P_{损}=\triangleUI_{2}=910^{5}W$$`,
    String.raw`$$x\inZ，a\neqb，AB\parallelBC$$`,
    String.raw`$$\left[-\dfrac{1}{3},1ight]∪\left[2,3ight]$$`,
    '$${x}_{AC}={v}_{A}2T+\\dfrac{1}{2}a{\\left(2Tight)}^{2}$$',
  ])('恢复有明确边界的粘连命令或残缺 right：%s', (source) => {
    const html = renderMathText(source, true)
    expect(html).toContain('class="katex"')
    expect(html).not.toContain('math-unparsed')
    expect(html).not.toContain('katex-error')
  })

  it('完整命令不按短前缀拆分，合法公式保持原样渲染', () => {
    const html = renderMathText(String.raw`$\sinh x+\cosh x+\infty+\triangleleft$`, true)
    expect(html).not.toContain('math-unparsed')
    expect(html).toContain(String.raw`\sinh x+\cosh x+\infty+\triangleleft`)
  })

  it('相邻 display 公式、空公式不会吞掉正文或后续公式', () => {
    const html = renderMathText('先 $$x$$$$y$$，再“$$$$”，“$$$$”，后 $$z$$。', true)
    expect(html.match(/class="katex"/g)).toHaveLength(3)
    expect(html).toContain('，再“”，“”，后 ')
    expect(html).not.toContain('math-unparsed')
  })

  it('识别 CMM-Math 的填空空白，保留真正的转义美元符号', () => {
    const html = renderMathText(String.raw`求 $x=$ \$ \qquad \$；价格 \$5`, true)
    expect(html.match(/class="katex"/g)).toHaveLength(2)
    expect(html).toContain('价格 $5')
    expect(html).not.toContain('math-unparsed')
  })

  it('无法确定题意的坏公式保留完整原文，不丢题句也不执行 HTML', () => {
    const source = String.raw`前文 $$\overset{⇌}$$ 后文 <img src=x>，下一式 $x+1$。`
    const html = renderMathText(source, true)
    expect(html).toContain('前文 ')
    expect(html).toContain('class="math-unparsed"')
    expect(html).toContain(String.raw`$$\overset{⇌}$$`)
    expect(html).toContain('后文 &lt;img src=x&gt;，下一式 ')
    expect(html.match(/class="katex"/g)).toHaveLength(1)
    expect(html).not.toContain('katex-error')
    expect(html).not.toContain('<img')
  })

  it('未配对的 display 分隔符保留原文并标记，不猜补公式', () => {
    const html = renderMathText('题目 $$\\frac{1}', true)
    expect(html).toContain('class="math-unparsed"')
    expect(html).toContain('题目 $$\\frac{1}')
  })
})

describe('缺失 display 分隔符的正文边界', () => {
  it.each([
    String.raw`函数$$y=f(x)在定义域$$\left[-\dfrac{3}{2},3ight]$$内可导，记$$y=f(x)的导函数为$$y=f'(x)，则不等式$$f'(x)\leqslant0$$的解集为(\quad)`,
    String.raw`若$$f(x)=A\sin(ωx+φ)(A>0,ω>0)的部分图象如图所示，则正确的是(\quad)`,
    String.raw`求$$x+1的值，下一式$$y=2$$。`,
  ])('正文不再被错位的公式分隔符吞入：%s', (source) => {
    const html = renderMathText(source, true)
    expect(html).not.toContain('math-unparsed')
    expect(html).not.toContain('katex-error')
    expect(html).not.toContain('katex-display')
    expect(html).toContain('class="katex"')
  })

  it('中文下标和 text 分组保持完整，正文中的 HTML 仍被转义', () => {
    const html = renderMathText(
      String.raw`功率$$P_{损}=\triangleUI_{2}的值，<img src=x>，$$\text{速度}v=3$$`,
      true,
    )
    expect(html).not.toContain('math-unparsed')
    expect(html).toContain('损')
    expect(html).toContain('速度')
    expect(html).toContain('&lt;img src=x&gt;')
    expect(html).not.toContain('<img')
  })
})
