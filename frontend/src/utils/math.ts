import katex from 'katex'
import 'katex/contrib/mhchem'
import { stripImageMarkers } from './question-content'

// Match empty display pairs too: adjacent $$x$$$$y$$ must not swallow prose.
// Escaped currency dollars are consumed before looking for formula delimiters.
const TEX_DELIMITERS =
  /\\\$|\$\$([\s\S]*?)\$\$|\\\[([\s\S]*?)\\\]|\\\(([\s\S]*?)\\\)|\$([^$\n]+?)\$/g
const JOINED_COMMANDS = [
  'triangle',
  'therefore',
  'because',
  'Rightarrow',
  'leqslant',
  'geqslant',
  'parallel',
  'Delta',
  'angle',
  'omega',
  'times',
  'cdot',
  'odot',
  'neq',
  'bot',
  'sin',
  'cos',
  'tan',
  'min',
  'ln',
  'pi',
  'in',
]
const commandSupport = new Map<string, boolean>()
const options = {
  throwOnError: true,
  strict: false,
  trust: false,
  output: 'htmlAndMathml',
} as const

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function supportedCommand(command: string) {
  if (!commandSupport.has(command)) {
    let supported = false
    try {
      katex.renderToString(command, options)
      supported = true
    } catch {
      // Only unknown, joined symbol commands are eligible for separation.
    }
    if (commandSupport.size >= 256) commandSupport.clear()
    commandSupport.set(command, supported)
  }
  return commandSupport.get(command)
}

function repairImportedTex(tex: string) {
  let repaired = tex
  // Some public records lost the backslash + r in \right. Restrict this
  // recovery to formulas that actually contain \left; never infer an operator.
  if (tex.includes('\\left')) {
    repaired = repaired.replace(/ight(?=[)\]|])/g, (word, offset: number) =>
      tex.slice(offset - 2, offset) === '\\r' ? word : '\\right',
    )
  }
  return repaired.replace(/\\([A-Za-z]+)/g, (full: string, command: string) => {
    // Preserve valid commands such as \sinh, \infty and \triangleleft.
    if (supportedCommand(full)) return full
    const prefix = JOINED_COMMANDS.find(
      (name) => command.startsWith(name) && /^[A-Za-z]+$/.test(command.slice(name.length)),
    )
    return prefix ? `\\${prefix} ${command.slice(prefix.length)}` : full
  })
}

// A coordinate list may wrap between complete tuples, never within a fraction,
// command argument or nested pair. This changes layout only, not source data.
function breakCoordinateList(tex: string) {
  if (tex.includes('\\begin')) return tex
  let braces = 0
  let pairs = 0
  let result = ''
  let previous = ''
  for (let index = 0; index < tex.length; index++) {
    const char = tex[index]
    const escaped = index > 0 && tex[index - 1] === '\\'
    if (!escaped) {
      if (char === '{') braces++
      if (char === '}') braces = Math.max(0, braces - 1)
      if (char === '(' || char === '[') pairs++
      if (char === ')' || char === ']') pairs = Math.max(0, pairs - 1)
    }
    result += char
    if (char === ',' && braces === 0 && pairs === 0 && /[)\]]/.test(previous)) {
      result += '\\allowbreak '
    }
    if (!/\s/.test(char)) previous = char
  }
  return result
}

// Escaped braces are enough to identify a standalone set even without TeX commands.
function hasBareMath(text: string) {
  return /\\[A-Za-z]+/.test(text) || /\\\{[^\n]*\\\}/.test(text)
}

function escapedProse(text: string) {
  // Heading commands carry prose; bare TeX must not leak into student text.
  const source = text.replace(/\\section\*?\{([^{}]*)\}/g, '$1')
  if (/\$\$|\\[\[\]()]|\$(?:[A-Za-z\\{]|[0-9]+[A-Za-z_^=+*/-])/.test(source)) {
    return '<span class="math-unparsed">' + escapeHtml(source) + '</span>'
  }
  return splitProse(source)
    .map(({ prose, text: part }) => {
      if (prose || !hasBareMath(part)) {
        return escapeHtml(part.replace(/\\([%&#])/g, '$1')).replace(/&lt;br\s*\/?&gt;/gi, '<br>')
      }
      const renderBareFormula = (tex: string, displayMode = false) => {
        try {
          return katex.renderToString(tex, { ...options, displayMode })
        } catch {
          try {
            return katex.renderToString(repairImportedTex(tex), { ...options, displayMode })
          } catch {
            return '<span class="math-unparsed">' + escapeHtml(tex) + '</span>'
          }
        }
      }
      const renderLines = (value: string) =>
        value
          .split('\n')
          .map((line) => (hasBareMath(line) ? renderBareFormula(line) : escapeHtml(line)))
          .join('\n')
      // Tables belong on a separate row, with their own horizontal viewport.
      // Otherwise a question's answer brackets get vertically centered on it.
      if (/\\begin\{/.test(part) && /\\(?:left|right)\b/.test(part)) {
        return '<span class="math-table">' + renderBareFormula(part, true) + '</span>'
      }
      const environments = /\\begin\{([A-Za-z*]+)\}[\s\S]*?\\end\{\1\}/g
      let cursor = 0
      let html = ''
      for (const match of part.matchAll(environments)) {
        const index = match.index ?? 0
        html += renderLines(part.slice(cursor, index))
        html += '<span class="math-table">' + renderBareFormula(match[0], true) + '</span>'
        cursor = index + match[0].length
      }
      return html + renderLines(part.slice(cursor))
    })
    .join('')
}

function renderDelimitedMath(value: string | null | undefined, inline = false) {
  const source = String(value ?? '')
    // Repair the known JSON \f decoding issue without changing other controls.
    .replace(/\u000c(?=rac\b)/g, '\\f')
    .replace(/([（(])\\q?quad\s*([）)])/g, '$1　$2')
    // CMM-Math uses escaped dollars around answer-space commands.
    .replace(/\\\$\s*(\\q?quad)\s*\\\$/g, (_, space: string) => `$${space}$`)
  let cursor = 0
  let output = ''

  for (const match of source.matchAll(TEX_DELIMITERS)) {
    const index = match.index ?? 0
    output += escapedProse(source.slice(cursor, index))
    cursor = index + match[0].length
    if (match[0] === '\\$') {
      output += '$'
      continue
    }
    const tex = match[1] ?? match[2] ?? match[3] ?? match[4] ?? ''
    if (!tex.trim()) {
      output += escapeHtml(tex)
      continue
    }
    const displayMode = !inline && (match[1] !== undefined || match[2] !== undefined)
    const englishPhrase =
      /^[A-Za-z\s'’.,!?;:-]+$/.test(tex) &&
      /\s/.test(tex.trim()) &&
      /\b(?:would|could|should|were|was|is|are|am|have|has|had|will|shall|if)\b/i.test(tex)
    if (englishPhrase) {
      output += escapeHtml(tex.trim())
      continue
    }
    try {
      output += katex.renderToString(inline ? breakCoordinateList(tex) : tex, {
        ...options,
        displayMode,
      })
    } catch {
      try {
        const repaired = repairImportedTex(tex)
        output += katex.renderToString(inline ? breakCoordinateList(repaired) : repaired, {
          ...options,
          displayMode,
        })
      } catch {
        // A broken fragment must not replace the surrounding question with a
        // red KaTeX error, or disappear. Preserve exact, escaped source instead.
        output += `<span class="math-unparsed">${escapeHtml(match[0])}</span>`
      }
    }
  }
  return output + escapedProse(source.slice(cursor))
}

// Chinese prose outside TeX groups gives a reliable boundary when imported
// records omit a closing $$. Chinese subscripts and \text{...} stay grouped.
function splitProse(value: string) {
  const parts: { prose: boolean; text: string }[] = []
  let depth = 0
  let start = 0
  let prose = false
  for (let index = 0; index < value.length; index++) {
    if (value[index] === '{') depth++
    if (value[index] === '}') depth = Math.max(0, depth - 1)
    const next = depth === 0 && /[\u3400-\u9fff，。；：、！？“”]/.test(value[index])
    if (next !== prose) {
      if (index > start) parts.push({ prose, text: value.slice(start, index) })
      start = index
      prose = next
    }
  }
  if (start < value.length) parts.push({ prose, text: value.slice(start) })
  return parts
}

function renderMathFragment(source: string, inline = false) {
  const rendered = renderDelimitedMath(source, inline)
  if (!source.includes('$$')) return rendered
  const fragments = source.split('$$')
  const misplacedProse = fragments.some(
    (part, index) => index % 2 === 1 && splitProse(part).some((piece) => piece.prose),
  )
  if (!rendered.includes('class="math-unparsed"') && !misplacedProse) return rendered
  // Currency dollars and mixed delimiter syntaxes keep the ordinary parser.
  if (fragments.some((part) => /\$|\\\(|\\\[/.test(part))) return rendered
  const recovered = fragments
    .map((part, index) =>
      splitProse(part)
        .map(({ prose, text }) => {
          if (prose) return escapeHtml(text)
          if (index % 2 === 1 || /\\[A-Za-z]|[=^_]/.test(text)) {
            return renderDelimitedMath(`$$${text}$$`, true)
          }
          return escapeHtml(text)
        })
        .join(''),
    )
    .join('')
  // Accept only a fully renderable recovery; otherwise retain exact source.
  return recovered.includes('class="math-unparsed"') ? rendered : recovered
}

// Pipes inside formulas (e.g. $|x|$) and escaped pipes belong to the cell.
function tableCells(line: string) {
  const protectedText: string[] = []
  const protectedLine = line.replace(
    /\\\||\$\$[^\n]*?\$\$|\$[^$\n]*?\$|\\\([^\n]*?\\\)|\\\[[^\n]*?\\\]/g,
    (part) => `\u0000${protectedText.push(part) - 1}\u0000`,
  )
  const cells = protectedLine.trim().split('|')
  if (cells[0] === '') cells.shift()
  if (cells[cells.length - 1] === '') cells.pop()
  return cells.map((cell) =>
    cell.trim().replace(/\u0000(\d+)\u0000/g, (token, index: string) => {
      const part = protectedText[Number(index)] ?? token
      return part === '\\|' ? '|' : part
    }),
  )
}

export function renderMathText(value: string | null | undefined, inline = false) {
  const source = stripImageMarkers(String(value ?? ''))
  const lines = source.split('\n')
  let output = ''
  let start = 0
  for (let index = 0; index + 1 < lines.length; index++) {
    if (!lines[index].includes('|')) continue
    const headers = tableCells(lines[index])
    const separator = tableCells(lines[index + 1])
    if (
      headers.length < 1 ||
      separator.length !== headers.length ||
      !separator.every((cell) => /^:?-{3,}:?$/.test(cell))
    )
      continue
    const rows: string[][] = []
    let end = index + 2
    while (end < lines.length && lines[end].includes('|')) {
      const cells = tableCells(lines[end])
      if (cells.length !== headers.length) break
      rows.push(cells)
      end++
    }
    if (!rows.length) continue
    output += renderMathFragment(lines.slice(start, index).join('\n'), inline)
    const rowHtml = (cells: string[], tag: 'th' | 'td') =>
      '<tr>' +
      cells.map((cell) => `<${tag}>${renderMathFragment(cell, true)}</${tag}>`).join('') +
      '</tr>'
    output +=
      '<div class="math-table"><table class="question-table"><thead>' +
      rowHtml(headers, 'th') +
      '</thead><tbody>' +
      rows.map((row) => rowHtml(row, 'td')).join('') +
      '</tbody></table></div>'
    start = end
    index = end - 1
  }
  return output + renderMathFragment(lines.slice(start).join('\n'), inline)
}
