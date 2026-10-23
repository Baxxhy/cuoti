// Read-only audit of an exported question-bank JSONL file. No database writes.
// Each row: { id, question_text, options: [{key,text}], solution, usable? }.
import { readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { createServer } from 'vite'

const [input, output] = process.argv.slice(2)
if (!input || !output) {
  console.error('Usage: node frontend/scripts/audit-formulas.mjs input.jsonl report.json')
  process.exit(2)
}
const server = await createServer({
  root: fileURLToPath(new URL('..', import.meta.url)),
  configFile: false,
  server: { middlewareMode: true, watch: null },
  appType: 'custom',
})
try {
  const { renderMathText } = await server.ssrLoadModule('/src/utils/math.ts')
  const rows = (await readFile(resolve(input), 'utf8'))
    .split('\n')
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line))
  let fields = 0
  let formulas = 0
  const findings = []
  for (const row of rows) {
    const texts = [
      ['question', row.question_text ?? row.question ?? ''],
      ...(row.options || []).map((option) => [`option.${option.key}`, option.text]),
      ['solution', row.solution || ''],
    ]
    for (const [field, text] of texts) {
      const html = renderMathText(text, true)
      fields++
      formulas += (html.match(/class="katex"/g) || []).length
      if (html.includes('class="math-unparsed"')) {
        findings.push({
          id: row.id,
          content_hash: row.content_hash,
          field,
          eligible: Boolean(row.usable ?? (row.usable_for_practice && row.usable_for_auto_grade)),
        })
      }
    }
  }
  const report = {
    questions: rows.length,
    fields,
    formulas,
    unresolvedFields: findings.length,
    findings,
  }
  await writeFile(resolve(output), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ ...report, findings: undefined }))
  // A renderable formula is not proof that the source retained every operator.
  // Findings require source review, not an automatic mathematical rewrite.
  if (findings.length) process.exitCode = 1
} finally {
  await server.close()
}
