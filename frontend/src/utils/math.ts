import katex from 'katex'

// Match empty display pairs too: adjacent $$x$$$$y$$ must not swallow prose.
// Escaped currency dollars are consumed before looking for formula delimiters.
const TEX_DELIMITERS =
  /\\\$|\$\$([\s\S]*?)\$\$|\\\[([\s\S]*?)\\\]|\\\(([\s\S]*?)\\\)|\$([^$\n]+?)\$/g
const JOINED_COMMANDS = [
  'triangle',
  'therefore',
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

function escapedProse(text: string) {
  const escaped = escapeHtml(text)
  // Unpaired display delimiters stay visible, rather than dropping their text.
  return /\$\$|\\\[|\\\(/.test(text) ? `<span class="math-unparsed">${escaped}</span>` : escaped
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
      output += katex.renderToString(tex, { ...options, displayMode })
    } catch {
      try {
        output += katex.renderToString(repairImportedTex(tex), { ...options, displayMode })
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

export function renderMathText(value: string | null | undefined, inline = false) {
  const source = String(value ?? '')
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
