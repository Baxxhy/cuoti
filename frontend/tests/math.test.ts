import { describe, expect, it } from 'vitest'
import { renderMathText } from '../src/utils/math'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

describe('数学公式文本渲染', () => {
  it('化学反应式和物理单位使用同一个安全公式渲染器', () => {
    const html = renderMathText(String.raw`$\ce{2H2 + O2 -> 2H2O}$ 与 $\pu{9.8 m/s2}$`)
    expect(html.match(/class="katex"/g)).toHaveLength(2)
    expect(html).not.toContain('math-unparsed')
  })
  it('未闭合的行内公式提示核对，美元价格不误判为公式错误', () => {
    expect(renderMathText('$x+1')).toContain('math-unparsed')
    expect(renderMathText(String.raw`$\frac{1}{2}`)).toContain('math-unparsed')
    expect(renderMathText('$5一份')).not.toContain('math-unparsed')
    expect(renderMathText(String.raw`价格 \$5`)).not.toContain('math-unparsed')
  })

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

describe('没有分隔符的源题公式', () => {
  it.each([
    String.raw`太阳鱼呼吸作用消耗的能量为1357 \mathrm{~J} \cdot \mathrm{m}^{-2} \cdot \mathrm{a}^{-1}`,
    String.raw`如图，若\angleAGE=32^{\circ}，则\angleGHC等于()`,
    String.raw`活性成分\mathrm{R}_3\mathrm{~N}在水中存在平衡：\mathrm{R}_3\mathrm{~N}+\mathrm{H}_2\mathrm{O}\rightleftharpoons\mathrm{R}_3\mathrm{NH}^{+}+\mathrm{OH}^{-}`,
    String.raw`解：\becauseAD//BC，\therefore\angleGHC=106^{\circ}`,
  ])('裸公式也按数学排版：%s', (source) => {
    const html = renderMathText(source, true)
    expect(html).toContain('class="katex"')
    expect(html).not.toContain('math-unparsed')
  })

  it('无分隔符表格完整渲染，分组内中文表头保留', () => {
    const html = renderMathText(
      String.raw`数据如下：\begin{array}{|c|c|}\hline\text{物质}&\text{现象}\\\hline\mathrm{A}&\text{变蓝}\\\hline\end{array}`,
      true,
    )
    expect(html).toContain('class="katex"')
    expect(html).not.toContain('math-unparsed')
    expect(html).toContain('math-table')
    expect(html).toContain('katex-display')
    expect(html).toContain('物质')
    expect(html).toContain('变蓝')
  })

  it('文档标题命令保留标题文本，百分号不露出转义符', () => {
    const html = renderMathText(String.raw`\section{消费情况扇形统计图}消费占25 \%`, true)
    expect(html).toContain('消费情况扇形统计图')
    expect(html).toContain('消费占25 %')
    expect(html).not.toContain('\\section')
    expect(html).not.toContain('math-unparsed')
  })

  it('损坏的裸命令同样进入格式核验，不假装成普通正文', () => {
    const html = renderMathText(String.raw`单位\unknownunit{J}，下一个 $x$`, true)
    expect(html).toContain('class="math-unparsed"')
    expect(html.match(/class="katex"/g)).toHaveLength(1)
    expect(html).toContain(String.raw`\unknownunit{J}`)
  })
})

it('裸矩阵的外层括号不与环境拆开', () => {
  const html = renderMathText('矩阵\\left(\\begin{array}{c}1\\\\2\\end{array}\\right)', true)
  expect(html).toContain('math-table')
  expect(html).not.toContain('math-unparsed')
})

describe('题库数据表格', () => {
  it('窄屏坐标列表在完整坐标之间允许换行，分数和嵌套括号保持完整', () => {
    const html = renderMathText('$A(-1,-2),B(-3,-1),C(-2,-3)$', true)
    expect(html.match(/class="mspace allowbreak"/g)).toHaveLength(2)
    expect(html).not.toContain('math-unparsed')
    for (const text of ['$f((1,2),(3,4))$', '$\\frac{(1,2),(3,4)}{2}$']) {
      expect(renderMathText(text, true)).not.toContain('allowbreak')
    }
  })
  it('支持单列表格及源数据中的换行标记', () => {
    const html = renderMathText('| 程序 |\n| --- |\n| INPUT $x$ <br> END |')
    expect(html).toContain('<table')
    expect(html.match(/<td>/g)).toHaveLength(1)
    expect(html).toContain('<br>')
    expect(html).not.toContain('&lt;br')
  })
  it('表头、数据和公式显示为表格，保留前后题句', () => {
    const html = renderMathText(
      '如下表\n| $x$ | 2 | 4 |\n| :---: | --- | --- |\n| $y$ | 3 | 5 |\n求函数关系。',
    )
    expect(html).toContain('<table class="question-table">')
    expect(html.match(/<th>/g)).toHaveLength(3)
    expect(html.match(/<td>/g)).toHaveLength(3)
    expect(html.match(/class="katex"/g)).toHaveLength(2)
    expect(html).toContain('如下表')
    expect(html).toContain('求函数关系。')
    expect(html).not.toContain(':---:')
  })
  it('绝对值和转义竖线不拆成列，表格中的 HTML 仍转义', () => {
    const html = renderMathText(
      '| 项目 | 值 |\n| --- | --- |\n| $|x|$ | <img src=x> |\n| A\\|B | 2 |',
    )
    expect(html.match(/<td>/g)).toHaveLength(4)
    expect(html).toContain('class="katex"')
    expect(html).toContain('A|B')
    expect(html).toContain('&lt;img')
    expect(html).not.toContain('<img')
  })
  it('表格中的范数双竖线保留原始数学命令', () => {
    const html = renderMathText('| 项目 | 值 |\n| --- | --- |\n| $\\|v\\|$ | 2 |')
    expect(html.match(/<td>/g)).toHaveLength(2)
    expect(html).toContain('\\|v\\|')
    expect(html).not.toContain('math-unparsed')
  })
  it('普通竖线文本及残缺表格保持原文，不猜测题目数据', () => {
    for (const source of ['A | B', '| A | B |\n| --- | --- |', '| A | B |\n| --- | --- |\n| 1 |']) {
      expect(renderMathText(source)).not.toContain('<table')
    }
  })
})
