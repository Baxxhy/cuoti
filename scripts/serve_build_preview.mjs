// Static H5 server for the compiled H5 artifact. It never serves repository files.
import http from "node:http";
import https from "node:https";
import {
  createReadStream,
  readFileSync,
  realpathSync,
  statSync,
} from "node:fs";
import { resolve, sep, extname } from "node:path";

const root = realpathSync(resolve("frontend/dist/build/h5"));
const upstream = new URL(
  process.env.ZHIWEI_BACKEND_URL || "http://127.0.0.1:8002",
);
const port = Number(process.env.ZHIWEI_PREVIEW_PORT || 8444);
const live = await fetch(new URL("/livez", upstream));
const identity = live.ok ? await live.json() : {};
if (identity.service !== "zhiwei-cangjie") throw new Error("Preview requires the Cangjie business service");

const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
};
function handle(req, res) {
  if (/^\/(api\/|uploads\/|reports\/)/.test(req.url)) {
    const request = http.request(
      {
        hostname: upstream.hostname,
        port: upstream.port,
        path: req.url,
        method: req.method,
        headers: { ...req.headers, host: upstream.host },
      },
      (response) => {
        res.writeHead(response.statusCode, response.headers);
        response.pipe(res);
      },
    );
    request.setTimeout(300_000, () => request.destroy());
    request.on("error", () => {
      if (!res.headersSent)
        res.writeHead(503, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ detail: "学习服务暂时无法连接，请重试" }));
    });
    req.pipe(request);
    return;
  }
  if (!["GET", "HEAD"].includes(req.method)) {
    res.writeHead(405);
    res.end();
    return;
  }
  try {
    const pathname = decodeURIComponent(
      new URL(req.url, "http://localhost").pathname,
    );
    const relative =
      pathname === "/" ? "index.html" : pathname.replace(/^\//, "");
    const file = realpathSync(resolve(root, relative));
    if (!file.startsWith(root + sep) || !statSync(file).isFile())
      throw new Error("not a build asset");
    res.writeHead(200, {
      "Content-Type": mime[extname(file)] || "application/octet-stream",
      "Cache-Control": "no-store",
    });
    if (req.method === "HEAD") res.end();
    else createReadStream(file).pipe(res);
  } catch {
    res.writeHead(404);
    res.end("Not found");
  }
}
const cert = process.env.ZHIWEI_PREVIEW_CERT,
  key = process.env.ZHIWEI_PREVIEW_KEY;
const server =
  cert && key
    ? https.createServer(
        { cert: readFileSync(cert), key: readFileSync(key) },
        handle,
      )
    : http.createServer(handle);
server.listen(port, "127.0.0.1", () =>
  console.log(
    `build_preview=${cert && key ? "https" : "http"}://127.0.0.1:${port}`,
  ),
);
