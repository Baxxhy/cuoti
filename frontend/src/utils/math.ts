import katex from 'katex'

const TEX_DELIMITERS = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|\$([^$\n]+?)\$/g

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

export function renderMathText(value: string | null | undefined, inline = false) {
  // 部分模型在结构化 JSON 中把 `\frac` 的 `\f` 误解为换页控制符，
  // 这里在渲染层恢复为 LaTeX 命令，兼容已经写入数据库的旧诊断结果。
  const source = String(value ?? '')
    .replace(/\u000c(?=rac\b)/g, '\\f')
    .replace(/([（(])\\q?quad\s*([）)])/g, '$1　$2')
  let cursor = 0
  let output = ''

  for (const match of source.matchAll(TEX_DELIMITERS)) {
    const index = match.index ?? 0
    output += escapeHtml(source.slice(cursor, index))

    const tex = match[1] ?? match[2] ?? match[3] ?? match[4] ?? ''
    const displayMode = !inline && (match[1] !== undefined || match[2] !== undefined)
    // A grammar phrase wrapped as TeX otherwise becomes multiplied letters,
    // losing word spaces. Keep recognizable English prose as escaped text.
    const englishPhrase =
      /^[A-Za-z\s'’.,!?;:-]+$/.test(tex) &&
      /\s/.test(tex.trim()) &&
      /\b(?:would|could|should|were|was|is|are|am|have|has|had|will|shall|if)\b/i.test(tex)
    if (englishPhrase) {
      output += escapeHtml(tex.trim())
      cursor = index + match[0].length
      continue
    }
    output += katex.renderToString(tex, {
      displayMode,
      throwOnError: false,
      strict: false,
      trust: false,
      output: 'htmlAndMathml',
    })
    cursor = index + match[0].length
  }

  return output + escapeHtml(source.slice(cursor))
}
