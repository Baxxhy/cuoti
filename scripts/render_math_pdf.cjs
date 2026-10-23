// Offline PDF layout using the same trusted formula renderer as the app.
const fs = require("node:fs");
const path = require("node:path");
const { createRequire } = require("node:module");
const root = path.resolve(__dirname, "..");
const frontend = path.join(root, "frontend");
const requireFrontend = createRequire(path.join(frontend, "package.json"));
const escape = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
async function main() {
  const input = JSON.parse(fs.readFileSync(0, "utf8"));
  const { build } = createRequire(requireFrontend.resolve("vite"))("esbuild");
  const bundle = await build({
    entryPoints: [path.join(frontend, "src/utils/math.ts")],
    bundle: true,
    platform: "node",
    format: "esm",
    write: false,
    logLevel: "silent",
  });
  const { renderMathText } = await import(
    "data:text/javascript;base64," +
      Buffer.from(bundle.outputFiles[0].text).toString("base64")
  );
  const render = (text) => {
    const html = renderMathText(String(text ?? ""), true);
    if (html.includes('class="math-unparsed"'))
      throw Error("存在需要校对的公式，请修正原文后再导出");
    return html;
  };
  const katexRoot = path.dirname(requireFrontend.resolve("katex/package.json"));
  const css = fs
    .readFileSync(path.join(katexRoot, "dist/katex.min.css"), "utf8")
    .replace(/url\(([^)]+)\)/g, (_, raw) => {
      const file = path.join(katexRoot, "dist", raw.replace(/["']/g, ""));
      const type = path.extname(file).slice(1);
      return `url(data:font/${type};base64,${fs.readFileSync(file).toString("base64")})`;
    });
  const body = (input.questions || [])
    .map((q, index) => {
      const options = (q.options || [])
        .map(
          (o, i) =>
            `<div class="option">${render(typeof o === "object" ? `${o.label || o.key || String.fromCharCode(65 + i)}. ${o.text || o.content || o.value || ""}` : o)}</div>`,
        )
        .join("");
      const images = (q.figures || [])
        .map((src) => `<img class="figure" src="${escape(src)}" />`)
        .join("");
      const solution = input.answers
        ? `<div class="answer"><strong>答案：</strong>${render(q.answer)}</div><div class="solution"><strong>解析：</strong>${render(q.explanation)}</div>`
        : '<div class="answer-space"></div>';
      return `<section class="question"><div class="stem"><span class="ordinal">${index + 1}.（${Number(q.score) || 10}分）</span>${render(q.question_text)}</div>${options}${q.formula ? `<div>${render(q.formula)}</div>` : ""}${images}${solution}</section>`;
    })
    .join("");
  const sheet = input.mode === "excel";
  const content = sheet
    ? input.cells.map((cell) => `<div class="sheet-cell" style="width:${Number(cell.width) || 450}px">${render(cell.text)}</div>`).join("")
    : `<h1>${render(input.title)}</h1>${body}`;
  const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; font-src data:; style-src 'unsafe-inline'"><style>${css}
  *{box-sizing:border-box}body{font:14px/1.9 'Noto Sans CJK SC','Microsoft YaHei',sans-serif;color:#202632;margin:0}h1{font-size:23px;font-weight:600;text-align:center;margin:0 0 25px;line-height:1.6}.question{margin-bottom:28px;break-inside:auto}.stem{white-space:pre-wrap;break-after:avoid}.ordinal{font-weight:600}.option{margin:5px 0 0 14px;white-space:pre-wrap}.answer,.solution{margin-top:12px;white-space:pre-wrap;orphans:3;widows:3}.solution{color:#333f50}.figure{display:block;max-width:100%;max-height:270px;object-fit:contain;margin:12px 0;break-inside:avoid;break-before:avoid}.answer-space{height:65px}.katex{white-space:normal;font-size:1.08em}.katex-display{margin:8px 0}.math-table{max-width:100%}strong{font-weight:600}table{border-collapse:collapse}td,th{padding:4px;border:1px solid #aaa}
  .sheet-cell{padding:6px;white-space:pre-wrap;overflow-wrap:anywhere;background:white;font-size:14px;line-height:1.9;margin-bottom:8px}
  </style></head><body>${content}</body></html>`;
  const { chromium } = requireFrontend("playwright");
  let executablePath = process.env.ZHIWEI_PDF_CHROMIUM;
  const bundled = path.join(frontend, ".playwright-browsers");
  if (!executablePath && fs.existsSync(bundled)) {
    for (const name of fs
      .readdirSync(bundled)
      .filter((n) => n.startsWith("chromium-"))
      .sort()
      .reverse()) {
      const candidate = path.join(bundled, name, "chrome-linux64/chrome");
      if (fs.existsSync(candidate)) {
        executablePath = candidate;
        break;
      }
    }
  }
  const libraries = path.join(
    frontend,
    ".playwright-libs/root/usr/lib/x86_64-linux-gnu",
  );
  const browser = await chromium.launch({
    executablePath,
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
    env: {
      ...process.env,
      LD_LIBRARY_PATH: [
        fs.existsSync(libraries) ? libraries : "",
        process.env.LD_LIBRARY_PATH,
      ]
        .filter(Boolean)
        .join(":"),
    },
  });
  try {
    const page = await browser.newPage({ javaScriptEnabled: false });
    await page.route("**/*", (route) => route.abort());
    await page.setContent(html, { waitUntil: "load", timeout: 15000 });
    await page.evaluate(() => document.fonts.ready);
    if (sheet) {
      const results = [];
      for (const element of await page.locator(".sheet-cell").all()) {
        // Preserve wide formula bodies too, instead of clipping to a worksheet cell.
        const width = await element.evaluate((node) => node.scrollWidth);
        await element.evaluate((node, width) => { node.style.width = `${width}px`; }, width);
        const box = await element.boundingBox();
        const png = await element.screenshot({ type: "png" });
        results.push({ png: png.toString("base64"), width: box.width, height: box.height });
      }
      process.stdout.write(JSON.stringify(results));
      return;
    }
    // A4 content width is 176 mm. Fit individual unbreakable formulas only;
    // ordinary prose keeps its readable font size and natural page wrapping.
    await page.setViewportSize({ width: 665, height: 1000 });
    await page.emulateMedia({ media: "print" });
    await page.evaluate(() => {
      for (const formula of document.querySelectorAll(".katex")) {
        const width = Math.max(formula.getBoundingClientRect().width, formula.scrollWidth,
          ...Array.from(formula.querySelectorAll(".base"), (base) => base.getBoundingClientRect().width));
        if (width > 660) {
          const size = parseFloat(getComputedStyle(formula).fontSize);
          formula.style.fontSize = `${size * 660 / width}px`;
          formula.style.display = "inline-block";
        }
      }
    });
    await page.pdf({
      path: input.output,
      format: "A4",
      printBackground: true,
      margin: { top: "17mm", bottom: "19mm", left: "17mm", right: "17mm" },
      displayHeaderFooter: true,
      headerTemplate: "<span></span>",
      footerTemplate:
        '<div style="width:100%;text-align:center;font:10px sans-serif;color:#667085">第 <span class="pageNumber"></span> 页</div>',
    });
  } finally {
    await browser.close();
  }
}
main().catch(() => {
  console.error("PDF公式排版失败，请检查公式或本地Chromium环境");
  process.exit(1);
});
